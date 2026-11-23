# guin-site-setup

Creates a **fresh `guin.localhost`** on the local **Frappe / ERPNext version-16** bench (macOS), installs the Guin (Retailers) app set, builds, migrates, checks the site serves, and **stops the bench** at the end.

Same workflow and same steps as the sibling skills **`vidira-site-setup`** and **`autorider-site-setup`**; only the site name and the app list differ. The app list mirrors Frappe Cloud: *Vidira - Application / Retailers / guinerp.m.frappe.cloud -> Apps*.

Works three ways (all do the same thing): **A.** the Python script (no AI), **B.** any AI tool, **C.** plain terminal commands.

Nothing here stores or sees your passwords. The MariaDB root password and the Administrator password are typed by **you** into bench's own prompts.

---

## What's in this folder

```
guin-site-setup/
├── README.md                     this file (tool-neutral)
├── SKILL.md                      same workflow as instructions for AI agents (Claude Code skill format)
├── apps.tsv                      the app list: order, name, repo, branch, public/private  <- edit here when apps change
├── scripts/setup_guin_site.py    launcher: runs the shared engine with this skill's defaults
└── logs/                         one log per script run (created automatically)
```

**Shared engine.** All logic (checks, clone, install, build, verify, stop, auto-fixes) lives in the sibling skill:
`../vidira-site-setup/scripts/setup_vidira_site.py` and `../vidira-site-setup/scripts/stop-bench.sh`.
Keep the folders together in `~/skillset/skills/vidira/`. The launcher adds `--apps-file <this apps.tsv> --site guin.localhost --no-use` and passes everything else through, so every engine flag works. `--no-use` means it does **not** change the bench's default site.

## What it sets up

Defaults (override with flags): bench `~/frappe/bt`, site `guin.localhost`. Everything Frappe-related stays under `~/frappe`. Apps already cloned in that bench are shared with the other sites and reused.

`frappe` is the bench; `erpnext` is installed by `bench new-site`. Then, in dependency order (`apps.tsv`):

| # | App | Repo | Branch | Access |
|---|---|---|---|---|
| 1 | payments | frappe/payments | version-16 | public |
| 2 | india_compliance | resilient-tech/india-compliance | version-16 | public |
| 3 | taraknath | Vidira-Innovations/taraknath | develop | **private** |
| 4 | pos_next (POSNext) | Build-Together-LLC/POSNext | BT | public |

Branches come straight from the Frappe Cloud site page (taraknath `develop` @ 47a389d, POSNext `BT` @ f7b3274). `taraknath`, `india_compliance` and `pos_next` all need erpnext.

## Requirements (already true on this Mac)

- macOS on Apple Silicon, Homebrew, git
- A **version-16 bench** (default `~/frappe/bt`), bench CLI 5.x
- Python **3.14**, Node **24** + Yarn, Redis, MariaDB **11.8** with the Frappe charset config (see `../vidira-site-setup/README.md`, "MariaDB charset")
- GitHub login with access to `Vidira-Innovations` (only for the private `taraknath`)

If the bench is not v16, the workflow **stops before changing anything**.

---

## A. Run the Python script (no AI)

In Terminal (an interactive terminal is needed for the password and GitHub prompts):

```bash
python3 ~/skillset/skills/vidira/guin-site-setup/scripts/setup_guin_site.py --dry-run   # look first, changes nothing
python3 ~/skillset/skills/vidira/guin-site-setup/scripts/setup_guin_site.py             # the real run
```

| Prompt | Answer |
|---|---|
| "Site guin.localhost already exists: keep / drop / abort" | `k` keep it and add missing apps; `d` drop and recreate (then type the site name to confirm). |
| GitHub login (only if `taraknath` is not reachable) | Follow the browser flow with the account that has access. |
| `MySQL root password:` (from bench) | Your MariaDB root password. |
| `Set Administrator password:` (from bench) | The password you will log in with. |
| "Install X with brew?" | Press Enter for yes. |

**Steps** (printed as `[n/9]`): `preflight` -> `auth` -> `redis` -> `site` -> `get-apps` -> `install-apps` -> `build-migrate` -> `verify` -> `stop`. It stops at the first failure, writes `logs/setup-<timestamp>.log`, and tells you how to resume with `--from <step>`. Known failures are fixed automatically.

**Flags** (all engine flags work): `--dry-run`, `--from STEP`, `--only STEP`, `--stop`, `--drop-existing`, `--keep-existing`, `--yes`, `--skip-private`, `--keep-running`, `--bench PATH`, `-v`, `--list-apps`, `--list-steps`. Full table: `../vidira-site-setup/README.md`.

```bash
setup_guin_site.py --drop-existing        # fresh site from scratch
setup_guin_site.py --from install-apps    # after fixing an install error
setup_guin_site.py --skip-private         # without taraknath (no GitHub login)
setup_guin_site.py --stop                 # stop everything of this bench
```

When it finishes:

```bash
cd ~/frappe/bt && bench start
# open http://guin.localhost:8000   (login: Administrator + the password you set)
```
The bench serves every site by hostname, so all your `*.localhost` sites work side by side without `bench use`.

---

## B. Use it with any AI tool

Give the tool shell access in a terminal on this Mac and paste:

```text
Read these files in ~/skillset/skills/vidira/guin-site-setup/ : README.md, SKILL.md, apps.tsv.
Then set up a fresh guin.localhost on my local Frappe v16 bench by following SKILL.md.

Rules:
- Verify the bench is version-16 first (Frappe branch/version, Python 3.14, Node 24). If not, stop and tell me; do not change an existing bench.
- taraknath is private: if GitHub isn't logged in, tell me to run `gh auth login` and `gh auth setup-git` myself.
- Prefer the script step by step: python3 scripts/setup_guin_site.py --dry-run first, then --only / --from steps.
- I type all passwords myself. Never ask me to paste one; never put one on a command line or in a log.
  Anything that prompts for a password (new-site, drop-site, gh auth login) I run in my own terminal.
- Ask before dropping an existing site. Never stop the bench while a restore/migrate/install job is running.
- Stop at the first error, show the log tail, fix the cause, resume.
- Finish by stopping the bench (../vidira-site-setup/scripts/stop-bench.sh) and give me a table of installed apps with versions.
```

- **Claude Code:** reads `SKILL.md` natively. For a `/guin-site-setup` slash command: `ln -s ~/skillset/skills/vidira/guin-site-setup ~/frappe/.claude/skills/guin-site-setup`. Run password-prompting commands yourself with the `!` prefix.
- **Codex / Cursor / Copilot / others with `AGENTS.md` or rules files:** add "For guin.localhost setup follow `skills/guin-site-setup/README.md`", or use the prompt above.
- **Chat-only assistants:** paste the commands from section C one by one and send back any errors.

---

## C. Plain terminal commands (no script, no AI)

```bash
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"
export GIT_TERMINAL_PROMPT=0
cd ~/frappe/bt

# 1. Bench must be v16
bench --version
git -C apps/frappe branch --show-current                  # version-16
grep '^__version__' apps/frappe/frappe/__init__.py        # 16.x.x
env/bin/python --version                                  # 3.14.x
node -v                                                   # v24.x

# 2. GitHub login (taraknath is private)
gh auth status || { brew install gh; gh auth login; }
gh auth setup-git

# 3. Redis (skip if `bench start` is already running)
redis-server config/redis_queue.conf &
redis-server config/redis_cache.conf &

# 4. Fresh site (asks MariaDB root password + Administrator password)
bench new-site guin.localhost --install-app erpnext
#    to start over:  bench drop-site guin.localhost   (archives a backup)

# 5. Get the apps (skip any already in ~/frappe/bt/apps)
bench get-app https://github.com/frappe/payments --branch version-16
bench get-app https://github.com/resilient-tech/india-compliance --branch version-16
bench get-app https://github.com/Vidira-Innovations/taraknath --branch develop
bench get-app https://github.com/Build-Together-LLC/POSNext --branch BT

# 6. Install on the site, in this order
for app in payments india_compliance taraknath pos_next; do
  bench --site guin.localhost install-app "$app" || break
done

# 7. Build, migrate, clear cache
bench build
bench --site guin.localhost migrate
bench --site guin.localhost clear-cache
bench --site guin.localhost list-apps

# 8. Stop the Redis servers you started in step 3
redis-cli -p 11000 shutdown; redis-cli -p 13000 shutdown nosave

# 9. Run it
bench start                                   # http://guin.localhost:8000
#    stop: Ctrl+C, or  bash ~/skillset/skills/vidira/vidira-site-setup/scripts/stop-bench.sh ~/frappe/bt
```

---

## D. Restore a Frappe Cloud backup onto guin.localhost (optional)

Download the `*-database.sql.gz` backup of the Guin site (guinerp) from Frappe Cloud (site -> Backups). **It replaces the whole database of `guin.localhost`.** The site and its apps must already exist (steps above). The backup of this site contains exactly `frappe`, `erpnext`, `payments`, `india_compliance`, `taraknath`, `pos_next`: all in this skill's app list.

```bash
# script: prompts for the MariaDB root password and the new Administrator password
python3 ~/skillset/skills/vidira/guin-site-setup/scripts/setup_guin_site.py --only restore \
  --backup ~/Downloads/<backup>-database.sql.gz --slim        # add --dry-run first to preview

# manual (no script, no AI)
cd ~/frappe/bt
bash ~/skillset/skills/vidira/vidira-site-setup/scripts/stop-bench.sh ~/frappe/bt
caffeinate -i bench --site guin.localhost --force restore ~/Downloads/<backup>-database.sql.gz --db-root-username root
#   (optional) empty the log tables now: section E
bench --site guin.localhost migrate
bench --site guin.localhost set-admin-password <the password you want>
bench --site guin.localhost scheduler disable
bench --site guin.localhost set-config mute_emails 1
bench --site guin.localhost clear-cache
bench --site guin.localhost clear-website-cache
```

The script also checks disk space and the backup's app list, and `--slim` empties the log tables before the migrate. Details, caveats (encryption key, uploaded files) and flags: `../vidira-site-setup/README.md`, section D. This restore takes about 2 minutes (115 MB backup).

## E. Slim the database (optional): empty log tables, keep all business data

**Policy: transactions and master data are never deleted**; only the log/queue/history tables in `../vidira-site-setup/slim-tables.txt` are emptied (version history, Data Import Log, Deleted Document, Access Log, Error Log, Route History, ...). This site is small (about 570 MB), so it frees little; the list matters most for `vidira` and `autorider`.

```bash
# script (uses the site's own DB user; asks you to type the site name)
python3 ~/skillset/skills/vidira/guin-site-setup/scripts/setup_guin_site.py --only slim              # --confirm skips the question, --dry-run previews

# manual
cd ~/frappe/bt
DB=$(python3 -c "import json;print(json.load(open('sites/guin.localhost/site_config.json'))['db_name'])")
sed -e '/^#/d' -e '/^[[:space:]]*$/d' -e 's/.*/TRUNCATE TABLE `&`;/' \
  ~/skillset/skills/vidira/vidira-site-setup/slim-tables.txt | mariadb -u root -p --force "$DB"
#   --force skips "table doesn't exist" errors (expected). TRUNCATE cannot be undone.
```

## Troubleshooting

Same table as `../vidira-site-setup/README.md`. The ones that matter most here:

| Symptom | Fix |
|---|---|
| `Repository not found` + GitHub password prompt | Not logged in or no org access: `gh auth login`. Never type a password into that prompt. |
| `Duplicate entry '<App Name>' for key 'PRIMARY'` after a failed install | `bench --site guin.localhost install-app <app> --force` (script does this for you). |
| Browser shows "Updating ... Status: 503" | `bench --site guin.localhost set-maintenance-mode off`, `bench set-config -g maintenance_mode 0`, then restart the bench. |
| `Redis ... Connection refused` | Redis isn't running: start it (step 3) or `bench start`. |
| `taraknath` fails on `requires-python` | It needs Python >= 3.14: the bench env must be 3.14 (the preflight checks this). |

## Safety notes

- Changes outside `~/frappe` are limited to Homebrew packages installed on your confirmation (`libmagic`, `gh`) and your `gh` login.
- **Stopping the bench** at the end stops everything belonging to that bench, so also the other sites' processes. It **refuses** while a restore/migrate/install/new-site job is running (exit 3). `--keep-running` skips it.
- Dropping a site only happens on your explicit choice plus typed confirmation; bench archives a backup.
- Apps are only **installed**; their own settings and data (POS profiles, etc.) still need configuring inside the site.

## Keeping it up to date

Edit **`apps.tsv`** only (TAB separated: `order  app_name  repo_url  branch  access`), then update the table in this README.
