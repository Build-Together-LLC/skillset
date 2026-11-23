---
name: autorider-site-setup
description: Create a fresh `autorider.localhost` Frappe site on the local version-16 bench, then clone (on the right branches) and install the AutoRider app set (payments, hrms, india_compliance, vidira_group, frappe_whatsapp, pos_next / POSNext), build, migrate, verify, and stop the bench. Use when the user asks to set up, recreate, reset or rebuild autorider.localhost, or to get and install the AutoRider apps locally. Checks the bench is v16 and GitHub auth first. Same workflow as vidira-site-setup with a different site and app list.
---

# AutoRider site setup (local Frappe v16 bench on macOS)

Builds `autorider.localhost` from scratch on the user's local bench with the same app set as the Frappe Cloud site "Vidira - Application / AutoRider" (autorider.m.frappe.cloud).

This skill is a thin layer on the sibling skill **`vidira-site-setup`**. The workflow, rules, known failures and the stop procedure are identical; only the site name and `apps.tsv` differ. **Read `../vidira-site-setup/SKILL.md` and follow it with these substitutions:**

| In vidira-site-setup | Here |
|---|---|
| site `vidira.localhost` | `autorider.localhost` |
| `$SKILL/apps.tsv` (11 apps) | this folder's `apps.tsv` (6 apps) |
| `scripts/setup_vidira_site.py` | `scripts/setup_autorider_site.py` (launcher; passes `--apps-file`, `--site autorider.localhost`, `--no-use`) |
| private apps: drive_bucket, vidira_group | private app: **vidira_group** only |
| `bench use <site>` at the end | **don't** run it: the bench serves each site by hostname, and the default site of other sites must stay unchanged |

- **App list, branches, order:** `apps.tsv` here (read it, don't retype it). `frappe` is the bench, `erpnext` comes from `new-site`.
- **Docs for humans / other tools:** `README.md`.
- **Stopping the bench:** `../vidira-site-setup/scripts/stop-bench.sh <BENCH>`.
- Default bench `~/frappe/bt`. Everything Frappe-related stays under `~/frappe`.
- `$SKILL` below = `~/skillset/skills/vidira/autorider-site-setup`; `$ENGINE` = `~/skillset/skills/vidira/vidira-site-setup/scripts/setup_vidira_site.py`.

## Ground rules (same as vidira-site-setup)

1. **Stop at the first failure**; read the log, fix the cause, resume from that step.
2. **Passwords:** prefer that the user types the MariaDB root and Administrator passwords into bench's own prompts (run the step with `!`, see below). If the user states them in chat and asks you to proceed, you may pass them once on the `bench new-site` command line (`--db-root-username root --db-root-password … --admin-password …`); never write them to files, logs or skill docs.
3. **Confirm before anything destructive** (dropping `autorider.localhost`, stopping a bench the user is using). Use AskUserQuestion.
4. Long commands run with `run_in_background`; chain them so they exit on the first failure.
5. Non-interactive shells need: `export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"`, `export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"`, `export GIT_TERMINAL_PROMPT=0`. (The script sets these itself.)
6. zsh does not word-split `$var`: no `set -- $spec` loops.

## Workflow (use the script, one step at a time)

```bash
python3 "$SKILL/scripts/setup_autorider_site.py" --dry-run             # always first: read-only checks, prints changes
python3 "$SKILL/scripts/setup_autorider_site.py" --only preflight      # 1. bench is v16: Frappe branch+version 16.x, Python 3.14, Node 24, MariaDB up, libmagic
python3 "$SKILL/scripts/setup_autorider_site.py" --only auth           # 2. GitHub login for vidira_group (private)
python3 "$SKILL/scripts/setup_autorider_site.py" --only redis          # 3. Redis for new-site/install/build/migrate
! python3 "$SKILL/scripts/setup_autorider_site.py" --only site         # 4. fresh site: USER runs it (prompts for passwords)
python3 "$SKILL/scripts/setup_autorider_site.py" --only get-apps       # 5. clone each app on its branch (skips ones already cloned)
python3 "$SKILL/scripts/setup_autorider_site.py" --only install-apps   # 6. install in dependency order; known failures auto-fixed
python3 "$SKILL/scripts/setup_autorider_site.py" --only build-migrate  # 7. build, migrate, clear-cache, check every app installed
python3 "$SKILL/scripts/setup_autorider_site.py" --only verify         # 8. start bench, GET /api/method/ping -> pong
python3 "$SKILL/scripts/setup_autorider_site.py" --stop                # 9. stop the bench, confirm ports free
```

The `!` prefix runs a command in the user's own session so they can type the prompts. The same applies to `gh auth login` (step 2) and to dropping an existing site (`--drop-existing`).

1. **Bench must be v16.** If `preflight` fails (not v16, wrong Python/Node), STOP and tell the user exactly what is wrong. Never modify or upgrade an existing bench yourself; offer options with AskUserQuestion. No bench at all: ask before `bench init bt --frappe-branch version-16 --python python3.14 --no-backups`.
2. **GitHub auth.** If `vidira_group` is unreachable, ask the user to run `! brew install gh`, `! gh auth login` (GitHub.com, HTTPS, web browser), `! gh auth setup-git`. If login works but the repo is still "not found", the account lacks access to `Vidira-Innovations`: tell the user; the rest can proceed only if they agree to `--skip-private`.
3. **Redis** must be up before new-site, install-app, build and migrate.
4. **Fresh site.** If `sites/autorider.localhost` exists, ask: keep (add missing apps) or drop and recreate (typed confirmation; bench archives a backup). Creation is `bench new-site autorider.localhost --install-app erpnext`; the user types the MariaDB root and Administrator passwords.
5-6. **Get and install** in `apps.tsv` order: payments, hrms, india_compliance, vidira_group, frappe_whatsapp, pos_next. Stop on the first failure.
7. **Build, migrate, clear-cache**, then `list-apps` must show frappe, erpnext and all six apps.
8. **Verify**; on HTTP 503 clear the maintenance flag (`set-maintenance-mode off`, `bench set-config -g maintenance_mode 0`) and restart the bench (the script does this).
9. **Stop the bench.** It stops everything of that bench, including the user's own `bench start`, and so also `vidira.localhost`; say so in the report. `--keep-running` skips it.

### Known failure modes (the script handles the first two)

| Symptom | Fix |
|---|---|
| `failed to find libmagic` (frappe_whatsapp) | `brew install libmagic`, re-install. |
| `Duplicate entry ... for key 'PRIMARY'` on Module Def after a failed install | Re-run `install-app <app> --force`. |
| `Redis ... Connection refused` on 11000/13000 | Start Redis (step 3); after a failed `new-site` answer `y` to roll back, then re-run. |
| `Repository not found` / GitHub password prompt | Auth problem (step 2). Never type a password into that prompt. |
| `pos_next` fails to install or the branch is missing | Branches are not shown on the Frappe Cloud site page; `apps.tsv` assumes `BT` (POSNext's default branch, targets v16). Check `git ls-remote --heads https://github.com/Build-Together-LLC/POSNext`, fix `apps.tsv`, delete `~/frappe/bt/apps/pos_next`, re-run `--only get-apps`. |
| Browser "Updating ... 503" | Maintenance flag, see step 8. |

## Optional: restore the Cloud backup, slim the database

Never part of a full run; only when the user asks, and confirm first (AskUserQuestion). Same rules as `../vidira-site-setup/SKILL.md` ("Optional: restore a Frappe Cloud backup, slim the database") and `README.md` sections D and E, with `autorider.localhost`:

```bash
python3 "$SKILL/scripts/setup_autorider_site.py" --only restore --backup <file>-database.sql.gz --dry-run   # then without --dry-run, run by the user (password prompts), add --slim to also empty the log tables
python3 "$SKILL/scripts/setup_autorider_site.py" --only slim --dry-run                                      # then --confirm after the user's OK
```

- The AutoRider backup contains exactly frappe, erpnext, payments, hrms, india_compliance, vidira_group, frappe_whatsapp, pos_next (all in `apps.tsv`); warn if a newer backup expects an app that is not cloned.
- After a restore: migrate, Administrator password of the user's choice, `scheduler disable`, `mute_emails 1`, clear caches (the script does all of it). Never stop the bench while a restore runs.
- **Slim policy: never delete transactions or master data**, only the log/queue/history tables in `../vidira-site-setup/slim-tables.txt`.

## Final report to the user

- Bench path and Frappe version, a table of installed apps (name, version, branch) from `list-apps`.
- Anything skipped, retried (`--force`) or changed on their system (`brew install libmagic`/`gh`).
- Which apps were reused from the bench vs newly cloned (only `pos_next` was new the first time).
- Whether the bench was stopped and the ports (8000, 9000, 11000, 13000) are free.
- How to use it: `cd ~/frappe/bt && bench start`, then http://autorider.localhost:8000, login `Administrator` with the password they set.
- Apps are only installed; their own credentials/settings (WhatsApp, POSNext POS profiles, banking, etc.) still need configuring in the site.
