# vidira-site-setup

Creates a **fresh `vidira.localhost`** on a local **Frappe / ERPNext version-16** bench (macOS), installs the full Vidira app set on the right branches, builds, migrates, checks the site actually serves, and **stops the bench** at the end.

It works three ways. They all do the same thing, so pick whichever you have:

| How | When |
|---|---|
| **A. Python script** (no AI) | Default. Also the fallback if no AI tool is available. |
| **B. Any AI tool** (Claude Code, Codex, Gemini CLI, Cursor, Copilot, ChatGPT with a terminal…) | You want an assistant to run it and handle errors. |
| **C. Plain terminal commands** (no script, no AI) | Extreme case: you want to type every command yourself. |

Nothing here stores or sees your passwords. The MariaDB root password and the new site's Administrator password are typed by **you** into bench's own prompts.

---

## What's in this folder

```
vidira-site-setup/
├── README.md                 this file (tool-neutral)
├── SKILL.md                  same workflow as instructions for AI agents (Claude Code skill format)
├── apps.tsv                  the app list: order, name, repo, branch, public/private  <- edit here when apps change
├── slim-tables.txt           log/queue tables the "slim" step empties (never transactions or master data)
├── scripts/
│   ├── setup_vidira_site.py  the whole workflow in Python (standard library only)
│   └── stop-bench.sh         stops one bench safely (also used by the script)
└── logs/                     one log file per script run (created automatically)
```

## What it sets up

Defaults (override with flags): bench `~/frappe/bt`, site `vidira.localhost`. Everything Frappe-related stays under `~/frappe`.

`frappe` and `erpnext` come from the bench / `new-site`. Then, in this order (from `apps.tsv`, mirroring the Frappe Cloud bench *Vidira - Unified / Vidira (Testing)*):

| # | App | Repo | Branch | Access |
|---|---|---|---|---|
| 1 | payments | frappe/payments | version-16 | public |
| 2 | hrms | frappe/hrms | version-16 | public |
| 3 | india_compliance | resilient-tech/india-compliance | version-16 | public |
| 4 | india_payroll | frappe/india-payroll | version-16 | public |
| 5 | india_banking_connector | aerele/india-banking-connector | version-16 | public |
| 6 | india_banking | aerele/india-banking | version-16 | public |
| 7 | btbanking | Build-Together-LLC/btbanking | Bt | public |
| 8 | raven | The-Commit-Company/Raven | main | public |
| 9 | frappe_whatsapp | Build-Together-LLC/frappe_whatsapp | BT | public |
| 10 | drive_bucket | Build-Together-LLC/drive_bucket | develop | **private** |
| 11 | vidira_group | Vidira-Innovations/vidira_group | develop | **private** |

The order is a real dependency order: hrms and india_compliance need erpnext, india_payroll needs hrms, btbanking needs india_banking_connector, vidira_group needs india_compliance.

## Requirements (already true on this Mac)

- macOS on Apple Silicon, Homebrew, git
- A **version-16 bench** (default `~/frappe/bt`): Frappe on branch `version-16`, bench CLI 5.x (`uv tool install frappe-bench`)
- Python **3.14** (uv), Node **24** (nvm) with Yarn, Redis, MariaDB **11.8** (`brew services start mariadb@11.8`)
- A GitHub account with access to `Build-Together-LLC` and `Vidira-Innovations` (only for the two private apps)

If the bench is not v16 the workflow **stops before changing anything**. It never upgrades or edits an existing bench for you.

---

## A. Run the Python script (no AI)

Open Terminal (an interactive terminal is needed for the password and GitHub prompts):

```bash
python3 ~/skillset/skills/vidira/vidira-site-setup/scripts/setup_vidira_site.py --dry-run   # look first: changes nothing, only prints
python3 ~/skillset/skills/vidira/vidira-site-setup/scripts/setup_vidira_site.py             # the real run
```

Works with the system `python3` (3.9+) or the uv Python 3.14; it uses only the standard library.

**What you will be asked, and what to type**

| Prompt | Answer |
|---|---|
| "Site vidira.localhost already exists: keep / drop / abort" | `k` to keep it and only add missing apps; `d` to drop and recreate (then type the site name to confirm). |
| GitHub login (only if the private repos are not reachable) | Follow the browser / one-time-code flow. Use the account that has access to the two orgs. |
| `MySQL root password:` (from bench) | Your MariaDB root password. |
| `Set Administrator password:` (from bench) | Choose the password you will log in with at http://vidira.localhost:8000. |
| "Install X with brew?" | Press Enter for yes. |

**Steps** (the script prints `[n/9] step` as it goes):

1. `preflight`: bench is v16 (Frappe branch + version, Python 3.14, Node 24, Yarn), MariaDB running, libmagic present
2. `auth`: GitHub login for the private repos (installs/uses `gh`)
3. `redis`: starts bench's two Redis servers if nothing is running
4. `site`: fresh site with ERPNext (asks before dropping an existing one)
5. `get-apps`: `bench get-app <repo> --branch <branch>` for every app (skips ones already cloned on the right branch)
6. `install-apps`: `bench install-app` in order, with automatic fixes for known failures (see Troubleshooting)
7. `build-migrate`: `bench build`, `migrate`, `clear-cache`, then checks every app is installed
8. `verify`: starts the bench and checks `/api/method/ping` returns `pong`
9. `stop`: stops the bench and confirms ports 8000, 9000, 11000, 13000 are free

It stops at the first failure, prints the last lines of the failing command, writes everything to `logs/setup-<timestamp>.log`, and tells you how to resume.

**Useful flags**

| Flag | Meaning |
|---|---|
| `--dry-run` | Run only read-only checks; print every change instead of doing it. |
| `--from STEP` | Resume from a step (preflight always runs first), e.g. `--from install-apps`. |
| `--only STEP` | Run just one step, e.g. `--only build-migrate`. |
| `--stop` | Just stop the bench (same as `--only stop`). |
| `--drop-existing` / `--keep-existing` | Decide what to do with an existing site without being asked. |
| `-y`, `--yes` | Answer the default to yes/no questions. Keeps an existing site unless `--drop-existing`. **Passwords are still prompted by bench.** |
| `--skip-private` | Skip `drive_bucket` and `vidira_group` (no GitHub login needed). |
| `--keep-running` | Don't stop the bench at the end. |
| `--bench PATH`, `--site NAME` | Use a different bench or site name (`$VIDIRA_BENCH` also works). |
| `--apps-file FILE` | Install the apps from another TAB-separated list (same format as `apps.tsv`) instead of this one. Logs go to a `logs/` folder next to that file. This is how `autorider-site-setup` reuses this script. |
| `--no-use` | Don't run `bench use <site>`, so the bench's default site stays unchanged. |
| `--only restore --backup FILE` | **Optional step** (section D): restore a Frappe Cloud database backup onto the site. `--slim` empties the log tables right after; `--no-scan` skips reading the backup's app list; `--db-root-user` (default `root`). |
| `--only slim` | **Optional step** (section E): empty the log tables in `slim-tables.txt`. `--tables-file FILE` uses another list. |
| `--confirm` | Confirms a destructive optional step (restore / slim) without typing the site name. `--yes` does **not** imply it. |
| `-v` | Also print every command's output on screen. |
| `--list-steps`, `--list-apps` | Print the steps / the app table and exit. |

Examples:

```bash
setup_vidira_site.py --drop-existing                     # fresh site from scratch
setup_vidira_site.py --from install-apps                 # after fixing an install error
setup_vidira_site.py --only build-migrate --keep-running # rebuild and leave the bench up
setup_vidira_site.py --stop                              # stop everything of this bench
```

When it finishes:

```bash
cd ~/frappe/bt && bench use vidira.localhost && bench start
# open http://vidira.localhost:8000  (login: Administrator + the password you set)
```

---

## B. Use it with any AI tool

Give the tool shell access in a terminal on this Mac and paste this prompt. It is tool-neutral:

```text
Read these files in ~/skillset/skills/vidira/vidira-site-setup/ : README.md, SKILL.md, apps.tsv.
Then set up a fresh vidira.localhost on my local Frappe v16 bench by following the workflow in SKILL.md.

Rules:
- First verify the bench is version-16 (Frappe branch/version, Python 3.14, Node 24). If it is not, stop and tell me; do not change an existing bench.
- Check GitHub login for the private repos; if not logged in, tell me to run `gh auth login` and `gh auth setup-git` myself.
- Prefer the script for each step: python3 scripts/setup_vidira_site.py --dry-run first, then the real steps (--only / --from).
- I type all passwords myself. Never ask me to paste a password, and never put one on a command line or in a log.
  Anything that prompts for a password (new-site, drop-site, gh auth login) must be run by me in my own terminal.
- Ask me before dropping an existing site. Stop at the first error, show the log tail, fix the cause, resume.
- Finish by stopping the bench (scripts/stop-bench.sh) and give me a table of installed apps with versions.
```

Tool-specific notes:

- **Claude Code:** it reads `SKILL.md` natively (frontmatter `name` / `description`). To make `/vidira-site-setup` a slash command, link this folder into a skills directory, e.g. `ln -s ~/skillset/skills/vidira/vidira-site-setup ~/frappe/.claude/skills/vidira-site-setup`. Commands that ask for passwords: run them yourself with the `!` prefix.
- **Codex / Cursor / Copilot / others that read `AGENTS.md` or rules files:** add one line to your project rules, e.g. "For vidira.localhost setup follow `skills/vidira-site-setup/README.md`", or just use the prompt above.
- **Chat-only assistants (no shell):** paste the commands from section C one at a time and send back any error output.

---

## C. Plain terminal commands (no script, no AI)

Replace nothing; copy block by block. Stop at the first error.

```bash
# 0. Tools on PATH (needed in a non-login shell; Terminal usually has them already)
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"
export GIT_TERMINAL_PROMPT=0
cd ~/frappe/bt

# 1. Bench must be v16
bench --version
git -C apps/frappe branch --show-current                  # version-16
grep '^__version__' apps/frappe/frappe/__init__.py        # 16.x.x
env/bin/python --version                                  # Python 3.14.x
node -v                                                   # v24.x
brew services list | grep mariadb                         # started   (else: brew services start mariadb@11.8)
brew list libmagic || brew install libmagic

# 2. GitHub login (private repos)
gh auth status || { brew install gh; gh auth login; }     # GitHub.com, HTTPS, web browser
gh auth setup-git

# 3. Redis (bench start would also do this; this is lighter)
redis-server config/redis_queue.conf &                    # port 11000
redis-server config/redis_cache.conf &                    # port 13000

# 4. Fresh site (prompts for MariaDB root password + Administrator password)
bench new-site vidira.localhost --install-app erpnext
#    existing site and you want a clean one:  bench drop-site vidira.localhost   (it archives a backup)

# 5. Get the apps (repo + branch exactly as in the table above)
bench get-app https://github.com/frappe/payments --branch version-16
bench get-app https://github.com/frappe/hrms --branch version-16
bench get-app https://github.com/resilient-tech/india-compliance --branch version-16
bench get-app https://github.com/frappe/india-payroll --branch version-16
bench get-app https://github.com/aerele/india-banking-connector --branch version-16
bench get-app https://github.com/aerele/india-banking --branch version-16
bench get-app https://github.com/Build-Together-LLC/btbanking --branch Bt
bench get-app https://github.com/The-Commit-Company/Raven --branch main
bench get-app https://github.com/Build-Together-LLC/frappe_whatsapp --branch BT
bench get-app https://github.com/Build-Together-LLC/drive_bucket --branch develop
bench get-app https://github.com/Vidira-Innovations/vidira_group --branch develop

# 6. Install on the site, in this order
for app in payments hrms india_compliance india_payroll india_banking_connector india_banking \
           btbanking raven frappe_whatsapp drive_bucket vidira_group; do
  bench --site vidira.localhost install-app "$app" || break
done

# 7. Build, migrate, clear cache
bench build
bench --site vidira.localhost migrate
bench --site vidira.localhost clear-cache
bench --site vidira.localhost list-apps

# 8. Stop the Redis servers you started in step 3
redis-cli -p 11000 shutdown; redis-cli -p 13000 shutdown nosave

# 9. Run it for real
bench use vidira.localhost && bench start       # http://vidira.localhost:8000
#    stop it again with Ctrl+C, or:  bash ~/skillset/skills/vidira/vidira-site-setup/scripts/stop-bench.sh ~/frappe/bt
```

---

## D. Restore a Frappe Cloud database backup (optional, after the site exists)

Use this to get the real data of the Cloud site into the local site. Download the `*-database.sql.gz` backup from Frappe Cloud (site -> Backups). **It replaces everything in the site's database**, so only do it on a local copy you can rebuild.

**Script** (prompts for the MariaDB root password and the new Administrator password; a full run never does this by itself):

```bash
python3 ~/skillset/skills/vidira/vidira-site-setup/scripts/setup_vidira_site.py --only restore \
  --backup ~/Downloads/<backup>-database.sql.gz --slim
# add --dry-run first to see every step without changing anything
```

What it does, in order:

1. Checks the file (gzip integrity, which Frappe version made it, free disk: about 12x the `.gz`).
2. Reads which apps the backup expects and **warns about any that are not cloned in the bench** (a restored site fails to load until they are, e.g. `insights` on `vidira.localhost`).
3. Asks you to type the site name, then restores (`caffeinate -i bench --site <site> --force restore <file>`; bench asks the MariaDB root password). About 15-30 minutes for a 2-3 GB `.gz`; don't interrupt it.
4. With `--slim`: empties the log tables (section E) *before* the migrate.
5. `bench migrate` (the bench is usually newer than the backup), asks for the Administrator password for this local copy, **disables the scheduler and mutes outgoing email** (so restored production data can't send real messages), clears caches.

**Manual commands** (no script, no AI):

```bash
cd ~/frappe/bt
bash ~/skillset/skills/vidira/vidira-site-setup/scripts/stop-bench.sh ~/frappe/bt     # nothing else may use the bench
caffeinate -i bench --site vidira.localhost --force restore ~/Downloads/<backup>-database.sql.gz --db-root-username root
#   bench asks "MySQL root password:". Don't interrupt it.
#   (optional) empty the log tables now: section E, manual commands
bench --site vidira.localhost migrate
bench --site vidira.localhost set-admin-password <the password you want>
bench --site vidira.localhost scheduler disable
bench --site vidira.localhost set-config mute_emails 1
bench --site vidira.localhost clear-cache
bench --site vidira.localhost clear-website-cache
```

Good to know: the backup has no site config, so **encrypted settings** (email/API passwords, integrations) won't decrypt until you copy the Cloud site's `encryption_key` (Frappe Cloud -> site -> Site Config) with `bench --site vidira.localhost set-config encryption_key "<key>"`. **Uploaded files** are not in a database backup; add them with `--with-public-files` / `--with-private-files` on the restore command.

## E. Slim the database (optional): empty log tables, keep all business data

A restored copy is mostly bloat. `tabVersion` alone was 15 GB on `vidira.localhost`.

**Policy: transactions (invoices, orders, delivery notes, stock and GL entries, serial and batch ...) and master data (items, customers, suppliers, accounts ...) are never deleted.** Only tables listed in `slim-tables.txt` are emptied: version history, API Request Log, e-Invoice Log, e-Waybill Log, Reorder Log, Route History, Error Log, Email Queue, Data Import Log, Deleted Document, ... Tables that don't exist on a site (their app isn't installed) are skipped. The same file lists, in comments, the log-like tables that are **left alone on purpose** (Communication, Comment, GST Return Log, `__global_search`, ...).

Result on this Mac: `vidira.localhost` 31.6 GB -> 13.7 GB, `autorider.localhost` 21.8 GB -> 11.7 GB, `guin.localhost` 840 MB -> 572 MB. What remains is real transaction data.

**Script** (uses the site's own database user, no root password; shows what it will empty, then asks you to type the site name):

```bash
python3 ~/skillset/skills/vidira/vidira-site-setup/scripts/setup_vidira_site.py --only slim              # asks to confirm
python3 ~/skillset/skills/vidira/vidira-site-setup/scripts/setup_vidira_site.py --only slim --confirm    # no question
python3 ~/skillset/skills/vidira/vidira-site-setup/scripts/setup_vidira_site.py --only slim --dry-run    # preview only
```

**Manual commands** (`TRUNCATE` cannot be undone; run them on the database of the site you mean):

```bash
cd ~/frappe/bt
DB=$(python3 -c "import json;print(json.load(open('sites/vidira.localhost/site_config.json'))['db_name'])")
mariadb -u root -p -e "select round(sum(data_length+index_length)/1024/1024) as MB from information_schema.tables where table_schema='$DB'"
sed -e '/^#/d' -e '/^[[:space:]]*$/d' -e 's/.*/TRUNCATE TABLE `&`;/' \
  ~/skillset/skills/vidira/vidira-site-setup/slim-tables.txt | mariadb -u root -p --force "$DB"
#   --force keeps going past "table doesn't exist" errors: expected, those tables belong to apps this site lacks
mariadb -u root -p -e "select round(sum(data_length+index_length)/1024/1024) as MB from information_schema.tables where table_schema='$DB'"
```

To clear one more table later, add its name (one per line, with the `tab` prefix) to `slim-tables.txt`. Only log, queue or history tables: if in doubt, leave it out.

## Troubleshooting (the script fixes the first two automatically)

| Symptom | Cause and fix |
|---|---|
| `failed to find libmagic` while installing `frappe_whatsapp` | macOS library missing: `brew install libmagic`, then install the app again. |
| `Duplicate entry '<App Name>' for key 'PRIMARY'` (Module Def) after a failed install | The failed attempt left a half-created module: `bench --site vidira.localhost install-app <app> --force`. |
| Browser shows **"Updating … Status: 503"** | Leftover maintenance flag. `bench --site vidira.localhost set-maintenance-mode off` and `bench set-config -g maintenance_mode 0`, then **restart** the bench (a running server keeps the old value). |
| `Redis ... Connection refused` on 11000 / 13000, or `Cannot connect to redis_cache` during build | Redis is not running. Start it (step 3) or `bench start`. After a failed `new-site`, answer `y` to roll back, start Redis, re-run. |
| `Repository not found` and a GitHub username/password prompt | Not logged in, wrong URL, or your account lacks access to the org. GitHub does not accept passwords: `gh auth login`. Never type a password into that prompt. |
| zsh loop turned a branch name into a folder (e.g. `apps/develop`) | zsh does not word-split `$var`. Use explicit commands or a `while read` loop; delete the stray folder under `apps/`. |
| Background jobs crash on macOS | In `~/frappe/bt/Procfile` use: `worker: FRAPPE_BACKGROUND_WORKERS_NOFORK=1 NO_PROXY=* bench worker-pool --num-workers 1 1>> logs/worker.log 2>> logs/worker.error.log` |
| `bench start` says a port is in use | Something is already running: `bash scripts/stop-bench.sh ~/frappe/bt`, or `lsof -nP -iTCP -sTCP:LISTEN \| grep -E ':(8000\|9000\|11000\|13000)'`. |

**MariaDB charset** (one-time, needed by Frappe; the script only warns if missing). `/opt/homebrew/etc/my.cnf`:

```ini
[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
bind-address = 127.0.0.1

[mysql]
default-character-set = utf8mb4
```
then `brew services restart mariadb@11.8`.

## Safety notes

- **Changes outside `~/frappe`** are limited to Homebrew packages the workflow may install on your confirmation (`libmagic`, `gh`) and your GitHub login for `gh`.
- **Stopping the bench** at the end stops *everything* belonging to that bench, including a `bench start` you had running in another terminal (and so every site on that bench). It never touches MariaDB or other apps' ports. Use `--keep-running` to skip it.
- **It refuses to stop while a bench job is running** (a `restore`, `migrate`, `backup`, `new-site`, `install-app`, `drop-site`), because killing one mid-way can corrupt a site database. `stop-bench.sh` prints the job and exits with code 3; wait for it to finish, then stop again. Override only if you are sure: `FORCE_STOP=1 bash scripts/stop-bench.sh ~/frappe/bt`.
- **Restore and slim are destructive and never part of a full run.** They only run when you ask (`--only restore` / `--only slim`) and confirm (typed site name or `--confirm`; `--yes` is not enough). Slim only ever touches tables named in `slim-tables.txt`: never transactions or master data.
- **Other sites share this bench and this script.** `autorider-site-setup` (a sibling folder) calls this engine with its own `apps.tsv`; keep both folders together in `~/skillset/skills/vidira/`.
- **Dropping a site** only happens on your explicit choice and typed confirmation; bench archives a backup under `sites/../archived_sites/`.
- The apps `btbanking`, `drive_bucket`, `vidira_group` (and `frappe_whatsapp`, `raven`, the banking apps) are only **installed**. Their own settings and credentials still need to be configured inside the site.

## Keeping it up to date

When the Frappe Cloud bench changes (new app, different branch), edit **`apps.tsv`** only. Columns, separated by TABs: `order  app_name  repo_url  branch  access`. The script, SKILL.md and the AI prompt all read that file. Update the table in this README to match.
