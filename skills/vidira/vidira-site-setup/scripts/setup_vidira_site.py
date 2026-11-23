#!/usr/bin/env python3
"""
setup_vidira_site.py - create a fresh `vidira.localhost` on a local Frappe version-16 bench,
clone + install the Vidira app set (apps.tsv), build, migrate, verify, and stop the bench.

No AI needed. Python 3.9+, standard library only. Run it in a normal terminal:

    python3 ~/skillset/skills/vidira/vidira-site-setup/scripts/setup_vidira_site.py            # full run
    python3 ~/skillset/skills/vidira/vidira-site-setup/scripts/setup_vidira_site.py --dry-run  # show what would happen
    python3 ~/skillset/skills/vidira/vidira-site-setup/scripts/setup_vidira_site.py --help

Passwords (MariaDB root, site Administrator) are typed by you into bench's own prompts.
This script never receives, stores or logs them.

It is also the shared engine for other site skills: `--apps-file other/apps.tsv --site other.localhost`
(see ../../autorider-site-setup). `--no-use` keeps the bench's default site unchanged.

Steps (use --from / --only to run part of it):
    preflight      bench is v16 (Frappe, Python 3.14, Node 24), MariaDB up, libmagic present
    auth           GitHub login so the private repos can be cloned
    redis          start bench's two Redis servers if nothing is running
    site           create a fresh site (asks before dropping an existing one)
    get-apps       bench get-app for every app in apps.tsv, on the right branch
    install-apps   bench install-app in dependency order, with auto-fixes for known failures
    build-migrate  bench build, migrate, clear-cache, then check every app is installed
    verify         start the bench and check /api/method/ping returns pong
    stop           stop the bench and confirm its ports are free

Optional steps (never part of a full run; always explicit with --only):
    restore        restore a Frappe Cloud database backup onto the site (--backup FILE), then migrate,
                   set the Administrator password, disable the scheduler, mute emails, clear caches
    slim           TRUNCATE the log/queue tables listed in slim-tables.txt to shrink the database
                   (uses the site's own DB user; asks you to type the site name, or pass --confirm)
"""
from __future__ import annotations

import argparse
import datetime as dt
import http.client
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
APPS_TSV = SKILL_DIR / "apps.tsv"
STOP_SH = SKILL_DIR / "scripts" / "stop-bench.sh"
LOG_DIR = SKILL_DIR / "logs"
HOME = Path.home()
DEFAULT_BENCH = HOME / "frappe" / "bt"
DEFAULT_SITE = "vidira.localhost"
STEPS = ["preflight", "auth", "redis", "site", "get-apps", "install-apps", "build-migrate", "verify", "stop"]
OPTIONAL_STEPS = ["restore", "slim"]  # never part of a full run; only via --only restore / --only slim
SLIM_TXT = SKILL_DIR / "slim-tables.txt"

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ
COLORS = {"ok": "32", "warn": "33", "err": "31", "step": "1;36", "dim": "2", "info": "0"}


# --------------------------------------------------------------------------- output

def say(msg: str, kind: str = "info") -> None:
    prefix = {"ok": "  [ok]   ", "warn": "  [warn] ", "err": "  [FAIL] ", "info": "  ", "dim": "  "}.get(kind, "")
    line = prefix + msg
    if USE_COLOR and kind in COLORS and kind != "info":
        line = f"\033[{COLORS[kind]}m{line}\033[0m"
    print(line, flush=True)


def banner(title: str) -> None:
    line = f"\n=== {title} ==="
    print(f"\033[{COLORS['step']}m{line}\033[0m" if USE_COLOR else line, flush=True)


class SetupError(Exception):
    def __init__(self, message: str, output: str = ""):
        super().__init__(message)
        self.output = output


class Result:
    def __init__(self, rc: int, output: str):
        self.rc = rc
        self.output = output


class App:
    def __init__(self, order: int, name: str, url: str, branch: str, access: str):
        self.order, self.name, self.url, self.branch, self.access = order, name, url, branch, access


def load_apps() -> list:
    if not APPS_TSV.exists():
        raise SetupError(f"apps list not found: {APPS_TSV}")
    apps = []
    for n, raw in enumerate(APPS_TSV.read_text().splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        cols = raw.split("\t")
        if len(cols) != 5 or not cols[0].strip().isdigit():
            raise SetupError(f"{APPS_TSV}:{n}: expected 5 TAB-separated columns (order, app, url, branch, access)")
        apps.append(App(int(cols[0]), cols[1].strip(), cols[2].strip(), cols[3].strip(), cols[4].strip().lower()))
    return sorted(apps, key=lambda a: a.order)


# --------------------------------------------------------------------------- environment

def find_node_bin() -> str:
    """Return a Node 24 bin dir from nvm if the current PATH has no Node 24 (non-login shells don't load nvm)."""
    try:
        v = subprocess.run(["node", "-v"], capture_output=True, text=True, env=_base_env()).stdout.strip()
        if v.startswith("v24."):
            return ""
    except OSError:
        pass
    root = HOME / ".nvm" / "versions" / "node"
    if root.is_dir():
        cands = []
        for d in root.iterdir():
            m = re.fullmatch(r"v24\.(\d+)\.(\d+)", d.name)
            if m and (d / "bin" / "node").exists():
                cands.append(((int(m.group(1)), int(m.group(2))), str(d / "bin")))
        if cands:
            return sorted(cands)[-1][1]
    return ""


def _base_env() -> dict:
    env = os.environ.copy()
    extra = ["/opt/homebrew/bin", "/opt/homebrew/sbin", str(HOME / ".local" / "bin")]
    env["PATH"] = ":".join(extra + [env.get("PATH", "")])
    return env


def build_env() -> dict:
    env = _base_env()
    node_bin = find_node_bin()
    if node_bin:
        env["PATH"] = node_bin + ":" + env["PATH"]
    env["GIT_TERMINAL_PROMPT"] = "0"  # wrong/private repo must fail, never hang on a username prompt
    env["NO_COLOR"] = "1"
    return env


# --------------------------------------------------------------------------- context + command runner

class Ctx:
    def __init__(self, args):
        self.args = args
        self.site = args.site
        self.dry = args.dry_run
        self.yes = args.yes
        self.verbose = args.verbose
        self.env = build_env()
        self.bench = None
        self.apps = []
        self.started = []          # Popen objects we started (redis / bench)
        self.reached_work = False  # True once preflight passed
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.log_path = LOG_DIR / f"setup-{dt.datetime.now():%Y%m%d-%H%M%S}.log"
        self.log_fh = open(self.log_path, "a", buffering=1)

    def log(self, text: str) -> None:
        self.log_fh.write(text + "\n")

    @property
    def tty(self) -> bool:
        return sys.stdin.isatty() and sys.stdout.isatty()


def run(ctx: Ctx, cmd: list, *, cwd=None, mutating=True, interactive=False, check=True,
        timeout=None, quiet=False, env_extra=None) -> Result:
    """Run a command. Output goes to the log file (and to the console with -v).
    Read-only commands (mutating=False) run even in --dry-run; mutating ones are only printed."""
    shown = shlex.join(str(c) for c in cmd)
    ctx.log(f"$ {shown}   (cwd={cwd})")
    if ctx.dry and mutating:
        say(f"[dry-run] {shown}", "dim")
        return Result(0, "")
    if not quiet:
        say(f"$ {shown}", "dim")
    cmd = [str(c) for c in cmd]
    env = {**ctx.env, **(env_extra or {})}  # env_extra carries secrets (e.g. MYSQL_PWD) so they never appear on a command line

    if interactive:
        if not ctx.tty:
            raise SetupError(f"this step is interactive (it asks for passwords or a login) and needs a real terminal: {shown}")
        rc = subprocess.call(cmd, cwd=cwd, env=env)
        ctx.log(f"(interactive command exit {rc})")
        if check and rc != 0:
            raise SetupError(f"command failed (exit {rc}): {shown}")
        return Result(rc, "")

    try:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1, errors="replace")
    except OSError as e:
        if check:
            raise SetupError(f"cannot run {cmd[0]}: {e}")
        return Result(127, str(e))

    tail = deque(maxlen=400)

    def reader():
        for line in proc.stdout:
            line = ANSI_RE.sub("", line.rstrip("\n"))
            tail.append(line)
            ctx.log(line)
            if ctx.verbose:
                print("     " + line, flush=True)

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    start = last_beat = time.time()
    while t.is_alive():
        t.join(1.0)
        now = time.time()
        if not ctx.verbose and not quiet and now - last_beat >= 30:
            say(f"   ... still running ({int(now - start)}s)", "dim")
            last_beat = now
        if timeout and now - start > timeout:
            proc.kill()
            raise SetupError(f"timed out after {timeout}s: {shown}", "\n".join(tail))
    proc.wait()
    out = "\n".join(tail)
    if check and proc.returncode != 0:
        say("last output:", "err")
        for line in list(tail)[-25:]:
            print("     " + line)
        raise SetupError(f"command failed (exit {proc.returncode}): {shown}\n     full log: {ctx.log_path}", out)
    return Result(proc.returncode, out)


def ask(ctx: Ctx, question: str, default: bool) -> bool:
    """Yes/no question. With --yes (or no terminal) the default answer is used. Never used for passwords."""
    if ctx.yes or not ctx.tty:
        say(f"{question} -> {'yes' if default else 'no'} (default, non-interactive)", "dim")
        return default
    ans = input(f"  ? {question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    return default if not ans else ans.startswith("y")


# --------------------------------------------------------------------------- small helpers

def port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def bench_cfg(ctx: Ctx) -> dict:
    try:
        return json.loads((ctx.bench / "sites" / "common_site_config.json").read_text())
    except (OSError, ValueError):
        return {}


def ports(ctx: Ctx) -> dict:
    cfg = bench_cfg(ctx)

    def p(key, default):
        v = cfg.get(key)
        if isinstance(v, int):
            return v
        m = re.search(r":(\d+)", v) if isinstance(v, str) else None
        return int(m.group(1)) if m else default

    return {"queue": p("redis_queue", 11000), "cache": p("redis_cache", 13000),
            "web": p("webserver_port", 8000), "socketio": p("socketio_port", 9000)}


def bench_cmd(ctx: Ctx, *args, **kw) -> Result:
    return run(ctx, ["bench", *args], cwd=ctx.bench, **kw)


def site_apps(ctx: Ctx) -> list:
    """Apps installed on the site (from the database, via `bench list-apps --format json`)."""
    r = bench_cmd(ctx, "--site", ctx.site, "list-apps", "--format", "json", mutating=False, check=False, quiet=True)
    i = r.output.find("{")
    if r.rc != 0 or i < 0:
        return []
    try:
        data = json.loads(r.output[i:r.output.rfind("}") + 1])
        return list(data.get(ctx.site, []))
    except ValueError:
        return []


def norm_url(u: str) -> str:
    u = u.strip().lower().rstrip("/")
    return u[:-4] if u.endswith(".git") else u


def remote_branch_exists(ctx: Ctx, app: App) -> bool:
    r = run(ctx, ["git", "ls-remote", "--heads", app.url, app.branch], mutating=False, check=False, quiet=True, timeout=60)
    return r.rc == 0 and bool(r.output.strip())


def ensure_libmagic(ctx: Ctx, force: bool = False) -> bool:
    if run(ctx, ["brew", "list", "libmagic"], mutating=False, check=False, quiet=True).rc == 0:
        return True
    if not (force or ask(ctx, "libmagic is missing (frappe_whatsapp needs it). Install with `brew install libmagic`?", True)):
        return False
    run(ctx, ["brew", "install", "libmagic"])
    return True


# --------------------------------------------------------------------------- step: preflight

def step_preflight(ctx: Ctx) -> None:
    bench = ctx.bench
    results, fatal = [], []

    def check(ok: bool, label: str, detail: str = "", hint: str = "", is_fatal: bool = True) -> None:
        results.append((ok, label, detail, is_fatal))
        if ok:
            say(f"{label}  {detail}", "ok")
        else:
            say(f"{label}  {detail}", "err" if is_fatal else "warn")
            if hint:
                say("   fix: " + hint, "dim")
            if is_fatal:
                fatal.append(label)

    check((bench / "sites").is_dir() and (bench / "apps" / "frappe").is_dir(), "bench directory", str(bench),
          "pass --bench /path/to/bench (or create one: bench init bt --frappe-branch version-16 --python python3.14 --no-backups)")
    if fatal:
        raise SetupError("No bench found. Nothing was changed.")

    bv = run(ctx, ["bench", "--version"], mutating=False, check=False, quiet=True)
    check(bv.rc == 0, "bench CLI", bv.output.strip().splitlines()[-1] if bv.output.strip() else "",
          "uv tool install frappe-bench")

    br = run(ctx, ["git", "-C", bench / "apps" / "frappe", "rev-parse", "--abbrev-ref", "HEAD"], mutating=False, check=False, quiet=True)
    check(br.output.strip() == "version-16", "frappe branch is version-16", f"(found: {br.output.strip() or 'unknown'})")

    ver = ""
    try:
        m = re.search(r'^__version__\s*=\s*"([^"]+)"', (bench / "apps" / "frappe" / "frappe" / "__init__.py").read_text(), re.M)
        ver = m.group(1) if m else ""
    except OSError:
        pass
    check(ver.startswith("16."), "frappe version is 16.x", f"(found: {ver or 'unknown'})")

    py = run(ctx, [bench / "env" / "bin" / "python", "--version"], mutating=False, check=False, quiet=True)
    check(py.output.strip().startswith("Python 3.14"), "bench Python is 3.14", f"(found: {py.output.strip() or 'missing env'})",
          "recreate the bench env with Python 3.14 (uv python install 3.14)")

    nv = run(ctx, ["node", "-v"], mutating=False, check=False, quiet=True)
    check(nv.output.strip().startswith("v24."), "Node is v24", f"(found: {nv.output.strip() or 'none'})", "nvm install 24")

    yv = run(ctx, ["yarn", "-v"], mutating=False, check=False, quiet=True)
    check(yv.rc == 0, "yarn", yv.output.strip(), "npm install -g yarn")

    check(shutil.which("git", path=ctx.env["PATH"]) is not None, "git installed")
    check(shutil.which("brew", path=ctx.env["PATH"]) is not None, "Homebrew installed", hint="https://brew.sh")

    if fatal:
        raise SetupError("This is not a ready v16 bench (" + ", ".join(fatal) + "). Nothing was changed. "
                         "Fix the items above, or point --bench at a v16 bench.")

    # MariaDB
    if not port_open(3306):
        say("MariaDB is not running on 127.0.0.1:3306", "warn")
        if ask(ctx, "Start it with `brew services start mariadb@11.8`?", True):
            run(ctx, ["brew", "services", "start", "mariadb@11.8"])
            if not ctx.dry:
                for _ in range(30):
                    if port_open(3306):
                        break
                    time.sleep(1)
    check(ctx.dry or port_open(3306), "MariaDB running", "127.0.0.1:3306", "brew services start mariadb@11.8")

    cnf = Path("/opt/homebrew/etc/my.cnf")
    has_cnf = cnf.exists() and "utf8mb4" in cnf.read_text()
    check(has_cnf, "MariaDB charset config (utf8mb4)", str(cnf), "see README.md section 'MariaDB charset'", is_fatal=False)

    ensure_libmagic(ctx)
    check(True, "libmagic", "(needed by frappe_whatsapp)") if run(
        ctx, ["brew", "list", "libmagic"], mutating=False, check=False, quiet=True).rc == 0 else say(
        "libmagic not installed: frappe_whatsapp will fail until `brew install libmagic`", "warn")

    ctx.reached_work = True
    say(f"log file: {ctx.log_path}", "dim")


# --------------------------------------------------------------------------- step: auth

def step_auth(ctx: Ctx) -> None:
    private = [a for a in ctx.apps if a.access == "private"]
    public = [a for a in ctx.apps if a.access != "private"]

    for a in public:
        if not remote_branch_exists(ctx, a):
            say(f"{a.name}: cannot see branch '{a.branch}' at {a.url} (apps.tsv out of date?)", "warn")
    if not private:
        say("no private repos selected: GitHub login not needed", "ok")
        return

    bad = [a for a in private if not remote_branch_exists(ctx, a)]
    if not bad:
        say("private repos reachable: " + ", ".join(a.name for a in private), "ok")
        return

    say("cannot reach private repo(s): " + ", ".join(f"{a.name} ({a.url} @ {a.branch})" for a in bad), "warn")
    if not ctx.tty and not ctx.dry:
        raise SetupError("GitHub login needed but there is no terminal. Run in a terminal:\n"
                         "     brew install gh && gh auth login && gh auth setup-git\n     then re-run with --from get-apps")

    gh = shutil.which("gh", path=ctx.env["PATH"])
    if not gh:
        if not ask(ctx, "GitHub CLI (gh) is not installed. Install with `brew install gh`?", True):
            raise SetupError("gh is required to log in to GitHub. Install it, run `gh auth login`, then re-run.")
        run(ctx, ["brew", "install", "gh"])
        gh = shutil.which("gh", path=ctx.env["PATH"]) or "gh"

    if run(ctx, [gh, "auth", "status"], mutating=False, check=False, quiet=True).rc != 0:
        say("Opening GitHub login (follow the browser/one-time-code prompts). Use the account that has access to the private orgs.", "info")
        run(ctx, [gh, "auth", "login", "--hostname", "github.com", "--git-protocol", "https", "--web"], interactive=True)
    run(ctx, [gh, "auth", "setup-git"])

    if ctx.dry:
        return
    bad = [a for a in private if not remote_branch_exists(ctx, a)]
    if bad:
        raise SetupError("Still cannot reach: " + ", ".join(f"{a.url} @ {a.branch}" for a in bad) +
                         "\n     The logged-in GitHub account probably lacks access to that organisation, or the branch name is wrong.\n"
                         "     Check with: gh auth status    (use --skip-private to continue without these apps)")
    say("private repos reachable", "ok")


# --------------------------------------------------------------------------- step: redis

def ensure_redis(ctx: Ctx) -> None:
    pt = ports(ctx)
    todo = [(n, pt[k]) for n, k in (("redis_queue", "queue"), ("redis_cache", "cache")) if not port_open(pt[k])]
    if not todo:
        say(f"Redis already running (ports {pt['queue']}, {pt['cache']})", "ok")
        return
    for name, port in todo:
        conf = ctx.bench / "config" / f"{name}.conf"
        if not conf.exists():
            bench_cmd(ctx, "setup", "redis")
        say(f"starting {name} on port {port}", "info")
        if ctx.dry:
            say(f"[dry-run] redis-server {conf}", "dim")
            continue
        fh = open(ctx.log_path, "a")
        ctx.started.append(subprocess.Popen(["redis-server", str(conf)], cwd=ctx.bench, env=ctx.env, stdin=subprocess.DEVNULL,
                                            stdout=fh, stderr=subprocess.STDOUT, start_new_session=True))
    if ctx.dry:
        return
    for _, port in todo:
        for _ in range(30):
            if run(ctx, ["redis-cli", "-p", port, "ping"], mutating=False, check=False, quiet=True).output.strip() == "PONG":
                break
            time.sleep(0.5)
        else:
            raise SetupError(f"Redis did not answer on port {port}. See {ctx.log_path}")
    say("Redis is up", "ok")


def step_redis(ctx: Ctx) -> None:
    ensure_redis(ctx)


# --------------------------------------------------------------------------- step: site

def step_site(ctx: Ctx) -> None:
    ensure_redis(ctx)
    site_dir = ctx.bench / "sites" / ctx.site
    create = True

    if site_dir.exists():
        a = ctx.args
        if a.drop_existing:
            decision = "drop"
        elif a.keep_existing or ctx.yes or not ctx.tty:
            decision = "keep"
        else:
            ans = input(f"  ? Site {ctx.site} already exists. [k]eep it and only add missing apps / "
                        f"[d]rop and recreate (fresh) / [a]bort  (k): ").strip().lower()
            decision = {"d": "drop", "a": "abort"}.get(ans[:1], "keep")

        if decision == "abort":
            raise SetupError("aborted by user. Nothing was changed.")
        if decision == "keep":
            say(f"keeping existing site {ctx.site}", "ok")
            create = False
        else:
            if not ctx.yes:
                typed = input(f"  ! This DROPS the database of {ctx.site} (it is archived with a backup under sites/../archived_sites). "
                              f"Type the site name to confirm: ").strip()
                if typed != ctx.site:
                    raise SetupError("confirmation did not match. Nothing was dropped.")
            say("dropping existing site: bench will ask for the MariaDB root password", "info")
            bench_cmd(ctx, "drop-site", ctx.site, interactive=True)
            if not ctx.dry and site_dir.exists():
                raise SetupError(f"{site_dir} still exists after drop-site. Remove it manually and re-run with --from site.")

    if create:
        say("creating the site: bench will ask for the MariaDB root password, then for the Administrator password", "info")
        bench_cmd(ctx, "new-site", ctx.site, "--install-app", "erpnext", interactive=True)
        if not ctx.dry:
            installed = site_apps(ctx)
            if "erpnext" not in installed:
                raise SetupError(f"site created but erpnext is not installed (found: {installed}). Re-run: --from site")
            say(f"site {ctx.site} created with: {', '.join(installed)}", "ok")
    if not ctx.args.no_use:
        bench_cmd(ctx, "use", ctx.site, check=False)


# --------------------------------------------------------------------------- step: get-apps

def step_get_apps(ctx: Ctx) -> None:
    for a in ctx.apps:
        d = ctx.bench / "apps" / a.name
        if d.exists():
            remote = run(ctx, ["git", "-C", d, "remote", "get-url", "upstream"], mutating=False, check=False, quiet=True)
            if remote.rc != 0:
                remote = run(ctx, ["git", "-C", d, "remote", "get-url", "origin"], mutating=False, check=False, quiet=True)
            branch = run(ctx, ["git", "-C", d, "rev-parse", "--abbrev-ref", "HEAD"], mutating=False, check=False, quiet=True)
            if norm_url(remote.output) == norm_url(a.url) and branch.output.strip() == a.branch:
                say(f"{a.name}: already cloned on {a.branch}", "ok")
            else:
                say(f"{a.name}: apps/{a.name} exists but is {remote.output.strip() or '?'} @ {branch.output.strip() or '?'} "
                    f"(expected {a.url} @ {a.branch}). Left untouched; fix or delete that folder and re-run.", "warn")
            continue
        say(f"{a.name}: cloning {a.url} @ {a.branch}", "info")
        bench_cmd(ctx, "get-app", a.url, "--branch", a.branch)
        if not ctx.dry and not d.exists():
            raise SetupError(f"get-app finished but apps/{a.name} does not exist (is the app name in apps.tsv right?)")
        say(f"{a.name}: done", "ok")


# --------------------------------------------------------------------------- step: install-apps

def install_one(ctx: Ctx, name: str) -> None:
    cmd = ["--site", ctx.site, "install-app", name]
    extra, libmagic_done = [], False
    for _ in range(3):
        try:
            bench_cmd(ctx, *cmd, *extra)
            return
        except SetupError as e:
            out = e.output or ""
            if "failed to find libmagic" in out and not libmagic_done:
                say("known issue: libmagic missing -> brew install libmagic, then retry", "warn")
                ensure_libmagic(ctx, force=True)
                libmagic_done = True
                continue
            if "Module Def" in out and re.search(r"Duplicate entry .* for key 'PRIMARY'", out) and "--force" not in extra:
                say("known issue: a previous failed attempt left a half-created module -> retry with --force", "warn")
                extra = ["--force"]
                continue
            raise


def step_install_apps(ctx: Ctx) -> None:
    ensure_redis(ctx)
    installed = set(site_apps(ctx))
    if not ctx.dry and "erpnext" not in installed:
        raise SetupError(f"site {ctx.site} does not exist or has no erpnext (found: {sorted(installed)}). Run the 'site' step first.")
    for a in ctx.apps:
        if a.name in installed:
            say(f"{a.name}: already installed", "ok")
            continue
        if not ctx.dry and not (ctx.bench / "apps" / a.name).exists():
            raise SetupError(f"apps/{a.name} is not cloned. Run the 'get-apps' step first.")
        say(f"{a.name}: installing on {ctx.site}", "info")
        install_one(ctx, a.name)
        say(f"{a.name}: installed", "ok")


# --------------------------------------------------------------------------- step: build-migrate

def step_build_migrate(ctx: Ctx) -> None:
    ensure_redis(ctx)  # without Redis the build leaves the asset cache stale
    say("bench build (a few minutes)", "info")
    bench_cmd(ctx, "build")
    say("bench migrate", "info")
    bench_cmd(ctx, "--site", ctx.site, "migrate")
    bench_cmd(ctx, "--site", ctx.site, "clear-cache")
    if ctx.dry:
        return
    installed = set(site_apps(ctx))
    missing = [a.name for a in ctx.apps if a.name not in installed]
    if missing or "erpnext" not in installed:
        raise SetupError(f"after migrate these apps are not installed on {ctx.site}: {missing}")
    say("all expected apps are installed", "ok")


# --------------------------------------------------------------------------- step: verify

def http_ping(ctx: Ctx):
    try:
        conn = http.client.HTTPConnection("127.0.0.1", ports(ctx)["web"], timeout=15)
        conn.request("GET", "/api/method/ping", headers={"Host": ctx.site})
        resp = conn.getresponse()
        return resp.status, resp.read().decode("utf-8", "replace")
    except OSError as e:
        return 0, str(e)


def stop_own_redis(ctx: Ctx) -> None:
    """`bench start` runs its own Redis on the same ports; free them if WE started them."""
    if not ctx.started:
        return
    pt = ports(ctx)
    run(ctx, ["redis-cli", "-p", pt["queue"], "shutdown"], mutating=True, check=False, quiet=True)
    run(ctx, ["redis-cli", "-p", pt["cache"], "shutdown", "nosave"], mutating=True, check=False, quiet=True)
    time.sleep(1)
    ctx.started = [p for p in ctx.started if p.poll() is None]


def start_bench(ctx: Ctx) -> None:
    say("starting the bench (bench start)", "info")
    if ctx.dry:
        say("[dry-run] bench start", "dim")
        return
    stop_own_redis(ctx)
    fh = open(ctx.log_path, "a")
    proc = subprocess.Popen(["bench", "start"], cwd=ctx.bench, env=ctx.env, stdin=subprocess.DEVNULL, stdout=fh,
                            stderr=subprocess.STDOUT, start_new_session=True)
    ctx.started.append(proc)
    web = ports(ctx)["web"]
    for i in range(240):
        if port_open(web):
            time.sleep(2)
            return
        if proc.poll() is not None:
            raise SetupError(f"bench start exited early (code {proc.returncode}). See {ctx.log_path}")
        if i and i % 30 == 0:
            say(f"   ... waiting for port {web} ({i}s)", "dim")
        time.sleep(1)
    raise SetupError(f"bench did not open port {web} within 240s. See {ctx.log_path}")


def restart_bench(ctx: Ctx) -> None:
    run(ctx, ["bash", STOP_SH, ctx.bench], check=False)
    ctx.started = []
    start_bench(ctx)


def step_verify(ctx: Ctx) -> None:
    web = ports(ctx)["web"]
    if port_open(web):
        say(f"a bench is already serving on port {web}: using it", "ok")
    else:
        start_bench(ctx)
        if ctx.dry:
            return
    code, body = http_ping(ctx)
    if code == 503:
        say("HTTP 503 (maintenance flag left over): clearing it and restarting the bench", "warn")
        bench_cmd(ctx, "--site", ctx.site, "set-maintenance-mode", "off", check=False)
        bench_cmd(ctx, "set-config", "-g", "maintenance_mode", "0", check=False)
        restart_bench(ctx)
        code, body = http_ping(ctx)
    if code == 200 and "pong" in body:
        say(f"http://{ctx.site}:{web}/api/method/ping -> pong", "ok")
    else:
        raise SetupError(f"site check failed: HTTP {code} {body[:200]!r}. See {ctx.log_path}")


# --------------------------------------------------------------------------- step: stop

def step_stop(ctx: Ctx) -> None:
    r = run(ctx, ["bash", STOP_SH, ctx.bench], check=False, quiet=True)
    if ctx.dry:
        return
    for line in r.output.splitlines():
        print("  " + line)
    for p in ctx.started:
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
    ctx.started = []
    if r.rc == 0:
        say("bench stopped, ports are free", "ok")
    elif r.rc == 3:
        say("NOT stopped: a bench job (restore/migrate/install...) is still running. Wait for it, then run --stop", "warn")
    else:
        say("some bench ports are still in use (see above)", "warn")


# --------------------------------------------------------------------------- optional steps: restore, slim

def read_site_config(ctx: Ctx) -> dict:
    try:
        return json.loads((ctx.bench / "sites" / ctx.site / "site_config.json").read_text())
    except (OSError, ValueError):
        raise SetupError(f"cannot read sites/{ctx.site}/site_config.json: does the site exist? (run the 'site' step first)")


def bench_job_running(ctx: Ctx) -> str:
    """Text of any long-running bench JOB of this bench (restore, migrate, ...). Empty string = idle."""
    pat = f"{ctx.bench}/env/bin/python.* frappe .*(restore|migrate|backup|new-site|install-app|uninstall-app|drop-site|reinstall)"
    return run(ctx, ["pgrep", "-fl", pat], mutating=False, check=False, quiet=True).output.strip()


def confirm_destructive(ctx: Ctx, what: str) -> None:
    """--confirm, or (in a terminal) type the site name. Never implied by --yes."""
    if ctx.args.confirm:
        return
    if ctx.dry:
        say(f"[dry-run] would ask you to confirm: {what}", "dim")
        return
    if not ctx.tty:
        raise SetupError(f"{what}. This cannot be undone; there is no terminal to ask, so re-run with --confirm.")
    typed = input(f"  ! {what}. This cannot be undone.\n    Type the site name ({ctx.site}) to confirm: ").strip()
    if typed != ctx.site:
        raise SetupError("confirmation did not match. Nothing was changed.")


def backup_apps(ctx: Ctx, f: Path) -> list:
    """Apps recorded as installed INSIDE a database backup (scans until the table is found; big dumps take minutes)."""
    inner = ('gzip -dc "$1"' if f.suffix == ".gz" else 'cat "$1"') + r' | grep -a -m1 "INSERT INTO \`tabInstalled Application\`"'
    r = run(ctx, ["bash", "-c", inner, "_", str(f)], mutating=False, check=False, quiet=True)
    rows = re.findall(r"\('([^']+)','[^']*','[^']*','[^']*','[^']*',\d+,\d+,(?:'([^']*)'|NULL),(?:'([^']*)'|NULL),(?:'([^']*)'|NULL)", r.output)
    return [(app, ver or "?") for _name, app, ver, _branch in rows if app]


def step_restore(ctx: Ctx) -> None:
    a = ctx.args
    if not a.backup:
        raise SetupError("restore needs the backup file:  --only restore --backup /path/to/xxx-database.sql.gz")
    f = Path(a.backup).expanduser().resolve()
    if not f.is_file():
        raise SetupError(f"backup file not found: {f}")
    if not (ctx.bench / "sites" / ctx.site).is_dir():
        raise SetupError(f"site {ctx.site} does not exist. Create it first (the 'site' step), then restore.")
    busy = bench_job_running(ctx)
    if busy:
        raise SetupError("a bench job is already running; wait for it:\n     " + busy.replace("\n", "\n     "))

    size = f.stat().st_size
    say(f"backup: {f.name}  ({size / 1e9:.2f} GB compressed)", "info")
    if f.suffix == ".gz":
        say("checking gzip integrity (about a minute per few GB)", "dim")
        run(ctx, ["gzip", "-t", f], mutating=False, quiet=True)
    head = run(ctx, ["bash", "-c", ('gzip -dc "$1"' if f.suffix == ".gz" else 'cat "$1"') + ' | head -c 1500', "_", str(f)],
               mutating=False, check=False, quiet=True).output
    m = re.search(r"-- version = (\S+)", head)
    say(f"made by Frappe {m.group(1) if m else '?'}; this bench runs {read_bench_frappe_version(ctx)} (migrate runs after the restore)", "ok")
    free = shutil.disk_usage(str(ctx.bench)).free
    need = size * 12
    check_ok = free > need
    say(f"disk: {free / 1e9:,.0f} GB free, about {need / 1e9:,.0f} GB needed (SQL is ~10x the .gz)", "ok" if check_ok else "err")
    if not check_ok:
        raise SetupError("not enough free disk space for the restore.")

    if not a.no_scan:
        say("reading which apps the backup expects (can take a few minutes on big files; --no-scan skips)", "dim")
        have = backup_apps(ctx, f)
        if have:
            cloned = {p.name for p in (ctx.bench / "apps").iterdir() if p.is_dir()}
            say("apps inside the backup: " + ", ".join(f"{n} {v}" for n, v in have), "info")
            missing = [n for n, _ in have if n not in cloned]
            if missing:
                say("NOT cloned in this bench: " + ", ".join(missing) + "  -> the site will fail to load until they are "
                    "cloned (bench get-app <repo> --branch <branch>) and the site is migrated", "warn")
            else:
                say("every app in the backup is cloned in this bench", "ok")
        else:
            say("could not read the app list from the backup (continuing)", "warn")

    ensure_redis(ctx)
    confirm_destructive(ctx, f"The restore REPLACES the whole database of {ctx.site}"
                        + (" and then EMPTIES the log tables in slim-tables.txt (--slim)" if a.slim else ""))
    say("restoring: bench asks for the MariaDB root password. This takes a while; don't interrupt it.", "info")
    cmd = ["bench", "--site", ctx.site, "--force", "restore", f, "--db-root-username", a.db_root_user]
    if shutil.which("caffeinate", path=ctx.env["PATH"]):
        cmd = ["caffeinate", "-i"] + cmd  # keep the Mac awake
    run(ctx, cmd, cwd=ctx.bench, interactive=True)

    if a.slim:
        say("slim: emptying the log/queue tables right after the restore (before migrate, so migrate has less to chew on)", "info")
        step_slim(ctx, already_confirmed=True)

    say("migrate (the bench is usually newer than the backup)", "info")
    bench_cmd(ctx, "--site", ctx.site, "migrate")
    if ctx.tty or ctx.dry:
        say("set the Administrator password for this local copy (the restore brought back Frappe Cloud's)", "info")
        bench_cmd(ctx, "--site", ctx.site, "set-admin-password", interactive=True)
    else:
        say("no terminal: skipped set-admin-password. Run: bench --site %s set-admin-password <password>" % ctx.site, "warn")
    say("local safety: scheduler off, outgoing email muted", "info")
    bench_cmd(ctx, "--site", ctx.site, "scheduler", "disable")
    bench_cmd(ctx, "--site", ctx.site, "set-config", "mute_emails", "1")
    bench_cmd(ctx, "--site", ctx.site, "clear-cache")
    bench_cmd(ctx, "--site", ctx.site, "clear-website-cache")
    if not ctx.dry:
        say(f"{ctx.site} restored from {f.name}", "ok")
    say("encrypted settings (email/API passwords) need the Cloud site's encryption_key: bench --site %s set-config encryption_key \"<key>\"" % ctx.site, "dim")
    say("uploaded files are not in a database backup; add them with: bench restore ... --with-public-files/--with-private-files", "dim")


def read_bench_frappe_version(ctx: Ctx) -> str:
    try:
        m = re.search(r'^__version__\s*=\s*"([^"]+)"', (ctx.bench / "apps" / "frappe" / "frappe" / "__init__.py").read_text(), re.M)
        return m.group(1) if m else "?"
    except OSError:
        return "?"


def load_slim_tables(ctx: Ctx) -> list:
    p = Path(ctx.args.tables_file).expanduser() if ctx.args.tables_file else SLIM_TXT
    if not p.is_file():
        raise SetupError(f"table list not found: {p}")
    tables = [ln.strip() for ln in p.read_text().splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    for t in tables:
        if not re.fullmatch(r"[A-Za-z0-9 _\-]+", t):
            raise SetupError(f"unsafe table name in {p}: {t!r}")
    return tables


def step_slim(ctx: Ctx, already_confirmed: bool = False) -> None:
    """TRUNCATE the log/queue tables listed in slim-tables.txt, using the site's OWN database user (no root password).
    Never touches transactions or master data: only tables named in slim-tables.txt."""
    cfg = read_site_config(ctx)
    for k in ("db_name", "db_user", "db_password"):
        if not cfg.get(k):
            raise SetupError(f"{k} missing in sites/{ctx.site}/site_config.json")
    db = cfg["db_name"]
    busy = bench_job_running(ctx)
    if busy:
        raise SetupError("a bench job (restore/migrate/...) is running on this bench; wait for it:\n     " + busy.replace("\n", "\n     "))
    tables = load_slim_tables(ctx)

    def q(sql: str, mutating: bool = False) -> str:
        return run(ctx, ["mariadb", "-u", cfg["db_user"], "-N", "-B", "-e", sql], mutating=mutating, quiet=True,
                   env_extra={"MYSQL_PWD": cfg["db_password"]}).output.strip()

    q("select 1")  # proves the login works before anything is changed
    inlist = ",".join("'" + t + "'" for t in tables)
    total = lambda: float(q(f"select ifnull(round(sum(data_length+index_length)/1024/1024),0) from information_schema.tables where table_schema='{db}'") or 0)
    before = total()
    rows = q(f"select table_name, table_rows, round((data_length+index_length)/1024/1024,1) from information_schema.tables "
             f"where table_schema='{db}' and table_name in ({inlist}) order by (data_length+index_length) desc")
    existing = [ln.split("\t") for ln in rows.splitlines() if ln.strip()]
    say(f"{ctx.site}: database {db} is {before:,.0f} MB", "info")
    for t, r, mb in existing:
        if float(mb) >= 1:
            say(f"   {t:<34} ~{int(float(r)):>10} rows {float(mb):>9,.1f} MB", "dim")
    say(f"{len(existing)} of {len(tables)} listed tables exist here ({len(tables) - len(existing)} skipped: their app is not installed)", "info")
    if not existing:
        return
    if not already_confirmed:
        confirm_destructive(ctx, f"TRUNCATE {len(existing)} log/queue tables in {ctx.site}")
    for t, _r, _mb in existing:
        q(f"TRUNCATE TABLE `{db}`.`{t}`", mutating=True)
    if ctx.dry:
        return
    after = total()
    say(f"{ctx.site}: {before:,.0f} MB -> {after:,.0f} MB  (freed {before - after:,.0f} MB)", "ok")


STEP_FUNCS = {
    "preflight": step_preflight, "auth": step_auth, "redis": step_redis, "site": step_site,
    "get-apps": step_get_apps, "install-apps": step_install_apps, "build-migrate": step_build_migrate,
    "verify": step_verify, "stop": step_stop, "restore": step_restore, "slim": step_slim,
}


# --------------------------------------------------------------------------- main

def resolve_bench(arg) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    if os.environ.get("VIDIRA_BENCH"):
        return Path(os.environ["VIDIRA_BENCH"]).expanduser().resolve()
    cwd = Path.cwd()
    if (cwd / "sites").is_dir() and (cwd / "apps" / "frappe").is_dir():
        return cwd
    return DEFAULT_BENCH


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="setup_vidira_site.py",
        description="Create a fresh vidira.localhost on a local Frappe v16 bench and install the Vidira apps.",
        epilog="Steps: " + ", ".join(STEPS) + ".  Passwords are typed into bench's own prompts; this script never sees them.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bench", help=f"bench directory (default: $VIDIRA_BENCH, the current directory if it is a bench, else {DEFAULT_BENCH})")
    p.add_argument("--site", default=DEFAULT_SITE, help=f"site name (default {DEFAULT_SITE})")
    p.add_argument("--apps-file", help="app list (TAB separated, same format as apps.tsv) to install instead of this skill's apps.tsv; "
                                       "logs go to a logs/ folder next to it. Used by other site skills (e.g. autorider-site-setup)")
    p.add_argument("--no-use", action="store_true", help="do not run `bench use <site>` (leave the bench's default site alone)")
    p.add_argument("-y", "--yes", action="store_true",
                   help="answer the default to yes/no questions (installs missing helpers, KEEPS an existing site unless --drop-existing). Passwords are still prompted by bench")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--drop-existing", action="store_true", help="if the site exists, drop it and create a fresh one (asks you to type the site name unless --yes)")
    g.add_argument("--keep-existing", action="store_true", help="if the site exists, keep it and only add missing apps (never ask)")
    p.add_argument("--skip-private", action="store_true", help="skip apps marked private in apps.tsv (no GitHub login needed)")
    p.add_argument("--keep-running", action="store_true", help="do not stop the bench at the end")
    p.add_argument("--dry-run", action="store_true", help="run only read-only checks; print every change instead of doing it")
    p.add_argument("--from", dest="from_step", choices=STEPS, help="start at this step (preflight always runs first)")
    p.add_argument("--only", choices=STEPS + OPTIONAL_STEPS,
                   help="run just this step (preflight runs first unless it is 'stop'). Optional steps that are never part of a full run: "
                        "'restore' (needs --backup FILE) and 'slim' (empties the log tables in slim-tables.txt)")
    p.add_argument("--backup", help="database backup (.sql.gz or .sql) for --only restore, e.g. the *-database.sql.gz downloaded from Frappe Cloud")
    p.add_argument("--confirm", action="store_true", help="confirm a destructive optional step (restore/slim) without typing the site name; --yes does NOT imply this")
    p.add_argument("--slim", action="store_true", help="restore: right after the restore (before migrate) also empty the log tables in slim-tables.txt "
                                                       "(transactions and master data are never touched)")
    p.add_argument("--no-scan", action="store_true", help="restore: skip reading the app list inside the backup (the scan can take minutes on big files)")
    p.add_argument("--db-root-user", default="root", help="restore: MariaDB root user (default root; bench prompts for the password)")
    p.add_argument("--tables-file", help="slim: use this table list instead of slim-tables.txt (one table name per line)")
    p.add_argument("--stop", action="store_true", help="shortcut for --only stop")
    p.add_argument("--list-steps", action="store_true", help="list the steps and exit")
    p.add_argument("--list-apps", action="store_true", help="list the apps from apps.tsv and exit")
    p.add_argument("-v", "--verbose", action="store_true", help="also print every command's output to the screen (always in the log file)")
    return p.parse_args(argv)


def main() -> int:
    global APPS_TSV, LOG_DIR
    args = parse_args()
    if args.apps_file:
        APPS_TSV = Path(args.apps_file).expanduser().resolve()
        LOG_DIR = APPS_TSV.parent / "logs"
    if args.list_steps:
        print("\n".join(STEPS))
        return 0
    try:
        apps_all = load_apps()
    except SetupError as e:
        print(f"ERROR: {e}")
        return 1
    if args.list_apps:
        for a in apps_all:
            print(f"{a.order:>2}  {a.name:<24} {a.branch:<10} {a.access:<8} {a.url}")
        return 0
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", args.site):
        print(f"ERROR: invalid site name {args.site!r}")
        return 1
    if sys.platform != "darwin":
        print("note: written for macOS + Homebrew; other systems are untested.")

    if args.stop:
        args.only = "stop"
    if args.only:
        selected = [args.only] if args.only in ("preflight", "stop") else ["preflight", args.only]
    elif args.from_step:
        selected = ["preflight"] + [s for s in STEPS[STEPS.index(args.from_step):] if s != "preflight"]
    else:
        selected = list(STEPS)

    ctx = Ctx(args)
    ctx.bench = resolve_bench(args.bench)
    ctx.apps = [a for a in apps_all if not (args.skip_private and a.access == "private")]
    if args.only == "stop":
        ctx.reached_work = True  # explicit request to stop: allowed even without preflight

    banner(f"Frappe site setup  |  bench: {ctx.bench}  |  site: {ctx.site}" + ("  |  DRY RUN" if ctx.dry else ""))
    say("steps: " + " -> ".join(selected), "dim")
    say(f"apps ({len(ctx.apps)}) from {APPS_TSV}: " + ", ".join(a.name for a in ctx.apps), "dim")

    rc = 0
    t0 = time.time()
    try:
        for s in selected:
            if s == "stop":
                continue  # always handled in `finally`
            banner(f"[{selected.index(s) + 1}/{len(selected)}] {s}")
            ts = time.time()
            STEP_FUNCS[s](ctx)
            say(f"{s} finished in {int(time.time() - ts)}s", "dim")
    except SetupError as e:
        print()
        say(str(e), "err")
        resume = f"--only {s}" if s in OPTIONAL_STEPS else f"--from {s}"
        say(f"fix the cause, then resume with:  setup_vidira_site.py {resume}   (log: {ctx.log_path})", "info")
        rc = 1
    except KeyboardInterrupt:
        print()
        say("interrupted by you (Ctrl+C)", "warn")
        rc = 130
    finally:
        wants_stop = "stop" in selected and ctx.reached_work
        if not args.keep_running and (wants_stop or ctx.started):
            banner("stop the bench")
            try:
                step_stop(ctx)
            except Exception as e:  # never hide the real result behind a stop problem
                say(f"could not stop the bench cleanly: {e}", "warn")
        elif args.keep_running and (ctx.started or "stop" in selected):
            say("--keep-running: leaving the bench running. Stop it later with: setup_vidira_site.py --stop", "warn")

    if rc == 0 and not ctx.dry and "build-migrate" in selected:
        banner("done")
        r = run(ctx, ["bench", "--site", ctx.site, "list-apps"], cwd=ctx.bench, mutating=False, check=False, quiet=True)
        for line in r.output.splitlines():
            if re.match(r"^\w+\s+\S+\s+\S+\s*$", line):
                print("  " + line)
        print(f"\n  Use it:  cd {ctx.bench} && bench use {ctx.site} && bench start")
        print(f"           http://{ctx.site}:{ports(ctx)['web']}   (login: Administrator)")
    print(f"\n  total {int(time.time() - t0)}s   log: {ctx.log_path}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
