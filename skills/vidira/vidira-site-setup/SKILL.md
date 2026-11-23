---
name: vidira-site-setup
description: Create a fresh `vidira.localhost` Frappe site on the local version-16 bench, then clone (on the right branches) and install the full Vidira app set, build, migrate, verify, and stop the bench. Use when the user asks to set up, recreate, reset or rebuild vidira.localhost, or to get and install the Vidira apps (hrms, india_compliance, india_payroll, india_banking, btbanking, raven, frappe_whatsapp, drive_bucket, vidira_group) on a local bench. Checks the bench is v16 and GitHub auth first.
---

# Vidira site setup (local Frappe v16 bench on macOS)

Builds `vidira.localhost` from scratch on the user's local bench and installs the same app set as the Frappe Cloud bench "Vidira - Unified / Vidira (Testing)".

- **App list, branches and install order:** `apps.tsv` in this folder (single source of truth; read it, don't retype it).
- **Stopping the bench:** `scripts/stop-bench.sh [BENCH_DIR]` in this folder.
- **Default bench dir:** `~/frappe/bt`. If the current directory already has `sites/` and `apps/`, use that. Everything Frappe-related stays under `~/frappe`; nothing goes in the home folder root.
- Call the skill's own folder `$SKILL` below: `~/skillset/skills/vidira/vidira-site-setup`.
- **Human/tool-neutral docs:** `README.md` (usage, flags, plain-terminal commands, troubleshooting).

## Prefer the script

The whole workflow below is implemented in `scripts/setup_vidira_site.py` (stdlib only; the user can also run it by hand with no AI). Use it instead of re-typing commands, one step at a time:

```bash
python3 "$SKILL/scripts/setup_vidira_site.py" --dry-run                 # always first: read-only checks, prints changes
python3 "$SKILL/scripts/setup_vidira_site.py" --only preflight          # Step 1 (+ tools check)
python3 "$SKILL/scripts/setup_vidira_site.py" --only auth               # Step 2
python3 "$SKILL/scripts/setup_vidira_site.py" --only get-apps           # Step 5   (also: --from get-apps ...)
python3 "$SKILL/scripts/setup_vidira_site.py" --only install-apps       # Step 6, known failures auto-fixed
python3 "$SKILL/scripts/setup_vidira_site.py" --only build-migrate      # Step 7
python3 "$SKILL/scripts/setup_vidira_site.py" --only verify             # Step 8
python3 "$SKILL/scripts/setup_vidira_site.py" --stop                    # Step 9
```

Run long steps with `run_in_background`; read `logs/setup-*.log` or the `[FAIL]` lines. Flags: `--bench`, `--site`, `--skip-private`, `--keep-running`, `--drop-existing`, `--yes`, `--apps-file FILE`, `--no-use` (see README). The sibling skill `autorider-site-setup` uses this same script with `--apps-file` + `--site autorider.localhost --no-use`.
**Never stop a bench while a restore/migrate/install/new-site job is running.** `stop-bench.sh` now refuses (exit 3, prints the job). Don't override with `FORCE_STOP=1` unless the user explicitly says so. In the final report, say when stopping the bench also stops other sites' processes.
**Steps that prompt for a password or a browser login cannot be run by you** (no terminal, and you must not see passwords): the `site` step (`new-site` / `drop-site`) and `gh auth login`. Have the user run them with `! python3 "$SKILL/scripts/setup_vidira_site.py" --only site` (or `--only auth`) in this session. The numbered steps below describe the same logic in full, for when the script can't be used.

## Ground rules

1. **Stop at the first failure.** Read the log, fix the cause, resume from that step. Never install an app on top of a failed one.
2. **Passwords:** prefer that the user types the MariaDB root password and the new site's Administrator password into bench's own prompts (have them run `! cd <bench> && bench new-site ...` themselves; the `!` prefix runs it in this session). If the user states them in chat and asks you to proceed, you may pass them once on the `bench new-site` command line (`--db-root-username root --db-root-password ... --admin-password ...`); never write them to files, logs or skill docs.
3. **Confirm before anything destructive** (dropping an existing site, killing a bench the user may be working in). Use AskUserQuestion.
4. **Long commands** (`get-app`, `install-app`, `build`, `migrate`) run with `run_in_background`, writing to a log in the scratchpad directory. Chain them in one background script that exits on the first failure, then read the `RESULT:` lines.
5. **Environment for every non-interactive command** (the shell Claude uses does not load the user's rc files):
   ```bash
   export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh" >/dev/null 2>&1
   export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"
   export GIT_TERMINAL_PROMPT=0   # a wrong/private repo must fail, not hang on a username prompt
   ```
6. **zsh does not word-split `$var`.** Do not loop with `set -- $spec`; it silently turns the branch into a folder name. Read `apps.tsv` with `while IFS=$'\t' read -r order app url branch access; do ... done < <(grep -v '^#' "$SKILL/apps.tsv")`, or write each command out explicitly.

## Step 1: Locate the bench and verify it is v16

```bash
cd <BENCH>                       # e.g. ~/frappe/bt
bench --version
git -C apps/frappe branch --show-current          # must be: version-16
grep -E '^__version__' apps/frappe/frappe/__init__.py   # must start with 16.
env/bin/python --version                          # must be 3.14.x
node -v                                           # must be v24.x
```

- **All good:** continue.
- **Not v16 (different branch, version, Python or Node):** STOP. Tell the user exactly what is wrong. Do not modify or upgrade an existing bench on your own; offer options with AskUserQuestion.
- **No bench exists:** ask the user whether to create one, then (from `~/frappe`): `bench init bt --frappe-branch version-16 --python python3.14 --no-backups`. Requires uv, Python 3.14 (`uv python install 3.14 --default`), nvm + Node 24 + Yarn, `uv tool install frappe-bench`.

Also verify, and fix only the cheap ones:

```bash
brew services list | grep mariadb@11.8          # must be "started"; else: brew services start mariadb@11.8
grep -q utf8mb4 /opt/homebrew/etc/my.cnf && echo "charset ok"   # needs utf8mb4 + utf8mb4_unicode_ci (see docs)
brew list libmagic >/dev/null 2>&1 || brew install libmagic     # frappe_whatsapp fails to install without it
```

If `my.cnf` lacks the Frappe charset block, tell the user (it needs a MariaDB restart); don't guess.

## Step 2: GitHub authentication (needed for the private repos)

`drive_bucket` and `vidira_group` are private (see the `access` column).

```bash
gh auth status
for each private app in apps.tsv:   GIT_TERMINAL_PROMPT=0 git ls-remote --heads <url> <branch>
```

- A private repo answering "not found" means not logged in, or the GitHub account isn't in that org.
- **If `gh` is missing or not logged in:** ask the user to run, in this session:
  ```
  ! brew install gh
  ! gh auth login          # GitHub.com -> HTTPS -> Login with a web browser
  ! gh auth setup-git
  ```
  Re-run the `ls-remote` check. If it still fails after login, the account lacks access to `Build-Together-LLC` / `Vidira-Innovations`: tell the user and stop (the rest can still be installed if the user explicitly agrees to skip those two apps).
- Also check that each branch exists (`ls-remote` prints a line). A missing branch means `apps.tsv` is out of date.

## Step 3: Start Redis (required for new-site, install-app, build, migrate)

Check ports first: `lsof -nP -iTCP -sTCP:LISTEN | grep -E ':(8000|9000|11000|13000)'`. If something is already running, it is probably the user's own `bench start`; that is fine to reuse, and Step 9 will stop it (tell them).

If nothing is running, start only the two Redis servers (lighter than the full bench), each with `run_in_background`:

```bash
cd <BENCH> && exec redis-server config/redis_queue.conf     # port 11000
cd <BENCH> && exec redis-server config/redis_cache.conf     # port 13000
```

Confirm: `redis-cli -p 11000 ping` and `redis-cli -p 13000 ping` both return `PONG`.

## Step 4: Fresh site `vidira.localhost`

```bash
ls <BENCH>/sites/vidira.localhost 2>/dev/null
```

- **Site exists:** ask the user (AskUserQuestion): drop and recreate, or keep and only install missing apps. Dropping is destructive. If they choose drop: take a backup first (`bench --site vidira.localhost backup --with-files`), then have them run `! cd <BENCH> && bench drop-site vidira.localhost` (prompts for the MariaDB root password; the site is archived under `archived_sites/`).
- **Create it (user types the passwords):**
  ```
  ! cd <BENCH> && bench new-site vidira.localhost --install-app erpnext
  ```
  It asks for "MySQL root password" (user's MariaDB root) and "Set Administrator password". Redis must be up (Step 3) or the ERPNext install fails and rolls back.
- Verify: `cat <BENCH>/sites/vidira.localhost/site_config.json` shows `installed_apps: ["frappe","erpnext"]` (redact `db_password`/`encryption_key`/secrets when echoing).
- Optional: `bench use vidira.localhost`.

## Step 5: Get the apps (clone + pip install + asset build)

For each row of `apps.tsv`, in order:

- If `<BENCH>/apps/<app>` already exists: compare `git -C apps/<app> remote get-url upstream` and `git branch --show-current` with the row. Same -> skip. Different -> ask the user before touching it.
- Otherwise: `bench get-app <url> --branch <branch>` (explicit values from the row).
- After each: confirm `apps/<app>` exists and is on the right branch.
- Failure "Repository not found" / credentials prompt = auth problem (Step 2) or wrong URL. Do not retype credentials into a prompt.

## Step 6: Install apps on the site, in `apps.tsv` order

```bash
bench --site vidira.localhost install-app <app>
```

One at a time, exit on first failure. Order encodes real dependencies: `hrms`/`india_compliance` need erpnext; `india_payroll` needs hrms; `btbanking` needs `india_banking_connector`; `vidira_group` needs erpnext + india_compliance.

Known failure modes:

| Symptom | Cause / fix |
|---|---|
| `failed to find libmagic` (frappe_whatsapp) | `brew install libmagic`, then re-install. |
| After that: `Duplicate entry '<App Name>' for key 'PRIMARY'` on Module Def | The failed first attempt left a half-created module. Re-run `install-app <app> --force`. |
| `Redis ... Connection refused` on 11000/13000 | Redis isn't running (Step 3). On a failed `new-site`, answer `y` to roll back, start Redis, re-run. |
| `Could not find app` / ModuleNotFound | App not cloned or not pip-installed: redo Step 5 for it (`bench get-app` installs it into `env`). |
| Required-app error | Install the missing required app first (check `required_apps` in `apps/<app>/<app>/hooks.py`). |

## Step 7: Build, migrate, clear cache

With Redis up (otherwise the build prints "Cannot connect to redis_cache" and the asset cache goes stale):

```bash
bench build
bench --site vidira.localhost migrate
bench --site vidira.localhost clear-cache
```

All three must succeed. Then `bench --site vidira.localhost list-apps` must list `frappe`, `erpnext` plus every app in `apps.tsv`.

## Step 8: Verify the site actually serves

Start the full bench (`cd <BENCH> && bench start`, `run_in_background`), wait until port 8000 listens, then:

```bash
curl -s -w "\nHTTP %{http_code}\n" -H "Host: vidira.localhost" http://127.0.0.1:8000/api/method/ping     # expect {"message":"pong"} / HTTP 200
```

- **HTTP 503 `SessionStopped` / "Updating" page:** leftover maintenance flag. Clear both: `bench --site vidira.localhost set-maintenance-mode off` and `bench set-config -g maintenance_mode 0`, then restart the bench (a running server keeps the old value).
- **Background worker crashing on macOS:** in `<BENCH>/Procfile` the worker line should be
  `worker: FRAPPE_BACKGROUND_WORKERS_NOFORK=1 NO_PROXY=* bench worker-pool --num-workers 1 1>> logs/worker.log 2>> logs/worker.error.log` (ask before editing the user's Procfile).

## Step 9: Stop the bench

Always finish by stopping whatever is running (whether you started it or the user did; say so in the summary):

```bash
bash "$SKILL/scripts/stop-bench.sh" <BENCH>
```

It stops the bench's processes (web, socketio, watch, scheduler, worker, redis, vite/esbuild helpers) and prints whether ports 8000, 9000, 11000, 13000 are free. It exits non-zero if something outside this bench holds a port; report that, don't kill it. MariaDB (Homebrew service) is left running on purpose.

## Optional: restore a Frappe Cloud backup, slim the database

Never part of a full run. Only when the user asks. Both are destructive: use AskUserQuestion to confirm the site and the file/list first. Details and manual commands: `README.md` sections D and E.

**Restore** (`--only restore --backup <file>-database.sql.gz [--slim]`), site must already exist with its apps:
1. Run it with `--dry-run` first (checks gzip integrity, the Frappe version that made the backup, free disk about 12x the `.gz`, and lists the apps the backup expects). **If the backup expects an app that is not cloned in the bench** (e.g. `insights`), tell the user before restoring; the site will not load until that app is cloned and the site migrated.
2. The real restore replaces the whole site database. It asks for the MariaDB root password and the Administrator password, so the user runs it (`! python3 ... --only restore ...`). If the user states the passwords in chat and asks you to run it, you may call `bench --site <site> --force restore <file> --db-root-username root --db-root-password ...` yourself (run it in the background with `caffeinate -i`, and never write the passwords to files/logs).
3. Afterwards: `migrate`, set the Administrator password the user wants, `scheduler disable`, `set-config mute_emails 1`, `clear-cache`, `clear-website-cache`. The scheduler and email stay off so restored production data can never send real messages.
4. Tell the user: encrypted settings need the Cloud `encryption_key`; uploaded files are not in a database backup.
5. A restore takes 15-30 min for 2-3 GB: wait for it; never stop the bench meanwhile (`stop-bench.sh` refuses while a restore runs).

**Slim** (`--only slim [--confirm]`): empties only the tables listed in `slim-tables.txt` (version history, API Request Log, e-Invoice Log, e-Waybill Log, Reorder Log, Route History, Error Log, Email Queue, ...). It uses the site's own DB user, so no root password is needed.
- **Policy: never delete transactions (invoices, orders, delivery notes, stock/GL entries, serial and batch, ...) or master data (items, customers, suppliers, accounts, ...).** Only logs / queues / history. If a table is not clearly one of those, leave it out; the comments in `slim-tables.txt` list log-like tables left alone on purpose (Communication, Comment, GST Return Log, `__global_search`, ...).
- Always `--dry-run` first (it prints the sizes), get the user's OK, then run with `--confirm`.
- To add tables: only after the user names or approves them; check the DocType first (module, not submittable, not a child table of a master).
- `--only restore ... --slim` runs slim right after the restore, before the migrate.

## Final report to the user

- Bench path and version (frappe version from `list-apps`).
- A table of installed apps: name, version, branch (from `list-apps`).
- Anything skipped, retried (e.g. `--force`) or changed on their system (e.g. `brew install libmagic`).
- Confirmation the bench is stopped and the ports are free.
- How to use it: `cd <BENCH> && bench use vidira.localhost && bench start`, then http://vidira.localhost:8000, login `Administrator` with the password they set.
- Note that `btbanking`, `drive_bucket`, `vidira_group` (and `frappe_whatsapp`/`raven`/banking apps) may need their own credentials or settings; the skill only installs them.
