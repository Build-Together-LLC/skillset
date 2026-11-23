---
name: guin-site-setup
description: Create a fresh `guin.localhost` Frappe site on the local version-16 bench, then clone (on the right branches) and install the Guin / Retailers app set (payments, india_compliance, taraknath, pos_next / POSNext), build, migrate, verify, and stop the bench. Use when the user asks to set up, recreate, reset or rebuild guin.localhost (guinerp), or to get and install the Guin apps locally. Checks the bench is v16 and GitHub auth first. Same workflow as vidira-site-setup with a different site and app list.
---

# Guin site setup (local Frappe v16 bench on macOS)

Builds `guin.localhost` from scratch on the user's local bench with the same app set as the Frappe Cloud site "Vidira - Application / Retailers / guinerp.m.frappe.cloud".

This skill is a thin layer on the sibling skill **`vidira-site-setup`**. The workflow, rules, known failures and the stop procedure are identical; only the site name and `apps.tsv` differ. **Read `../vidira-site-setup/SKILL.md` and follow it with these substitutions:**

| In vidira-site-setup | Here |
|---|---|
| site `vidira.localhost` | `guin.localhost` |
| `$SKILL/apps.tsv` (11 apps) | this folder's `apps.tsv` (4 apps) |
| `scripts/setup_vidira_site.py` | `scripts/setup_guin_site.py` (launcher; passes `--apps-file`, `--site guin.localhost`, `--no-use`) |
| private apps: drive_bucket, vidira_group | private app: **taraknath** only |
| `bench use <site>` at the end | **don't** run it: the bench serves each site by hostname, other sites' default must stay unchanged |

- **App list, branches, order:** `apps.tsv` here (read it, don't retype it). `frappe` is the bench, `erpnext` comes from `new-site`.
- **Docs for humans / other tools:** `README.md`. **Stopping the bench:** `../vidira-site-setup/scripts/stop-bench.sh <BENCH>`.
- Default bench `~/frappe/bt`. Everything Frappe-related stays under `~/frappe`.
- `$SKILL` below = `~/skillset/skills/vidira/guin-site-setup`.

## Ground rules (same as vidira-site-setup)

1. **Stop at the first failure**; read the log, fix the cause, resume from that step.
2. **Passwords:** prefer that the user types the MariaDB root and Administrator passwords into bench's own prompts (run the step with `!`). If the user states them in chat and asks you to proceed, you may pass them once on the `bench new-site` command line (`--db-root-username root --db-root-password … --admin-password …`); never write them to files, logs or skill docs.
3. **Confirm before anything destructive** (dropping `guin.localhost`, stopping a bench the user is using). Use AskUserQuestion.
4. **Never stop the bench while a restore/migrate/install/new-site job is running** (`stop-bench.sh` refuses with exit 3).
5. Long commands run with `run_in_background`; chain them so they exit on the first failure.
6. Non-interactive shells need: `export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"`, `export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"`, `export GIT_TERMINAL_PROMPT=0`. (The script sets these itself.)
7. zsh does not word-split `$var`: no `set -- $spec` loops (they silently mangle repo/branch arguments); call commands explicitly.

## Workflow (use the script, one step at a time)

```bash
python3 "$SKILL/scripts/setup_guin_site.py" --dry-run             # always first: read-only checks, prints changes
python3 "$SKILL/scripts/setup_guin_site.py" --only preflight      # 1. bench is v16: Frappe branch+version 16.x, Python 3.14, Node 24, MariaDB up
python3 "$SKILL/scripts/setup_guin_site.py" --only auth           # 2. GitHub login for taraknath (private)
python3 "$SKILL/scripts/setup_guin_site.py" --only redis          # 3. Redis for new-site/install/build/migrate
! python3 "$SKILL/scripts/setup_guin_site.py" --only site         # 4. fresh site: USER runs it (prompts for passwords), or see rule 2
python3 "$SKILL/scripts/setup_guin_site.py" --only get-apps       # 5. clone each app on its branch (skips ones already cloned)
python3 "$SKILL/scripts/setup_guin_site.py" --only install-apps   # 6. install in dependency order; known failures auto-fixed
python3 "$SKILL/scripts/setup_guin_site.py" --only build-migrate  # 7. build, migrate, clear-cache, check every app installed
python3 "$SKILL/scripts/setup_guin_site.py" --only verify         # 8. start bench, GET /api/method/ping -> pong
python3 "$SKILL/scripts/setup_guin_site.py" --stop                # 9. stop the bench, confirm ports free
```

1. **Bench must be v16.** If `preflight` fails (not v16, wrong Python/Node), STOP and tell the user exactly what is wrong. Never modify or upgrade an existing bench yourself; offer options with AskUserQuestion.
2. **GitHub auth.** If `taraknath` is unreachable: `! brew install gh`, `! gh auth login` (GitHub.com, HTTPS, web browser), `! gh auth setup-git`. If login works but the repo is "not found", the account lacks access to `Vidira-Innovations`: tell the user; the rest can proceed only if they agree to `--skip-private`.
3. **Redis** must be up before new-site, install-app, build and migrate. If orphaned Redis processes from an earlier run are on 11000/13000, reuse them and shut them down at the end (`redis-cli -p 11000 shutdown`, `redis-cli -p 13000 shutdown nosave`).
4. **Fresh site.** If `sites/guin.localhost` exists, ask: keep (add missing apps) or drop and recreate (typed confirmation; bench archives a backup). Creation: `bench new-site guin.localhost --install-app erpnext`.
5-6. **Get and install** in `apps.tsv` order: payments, india_compliance, taraknath, pos_next. Stop on the first failure. `taraknath` needs Python >= 3.14 and erpnext.
7. **Build, migrate, clear-cache**, then `list-apps` must show frappe, erpnext and all four apps.
8. **Verify**; on HTTP 503 clear the maintenance flag (`set-maintenance-mode off`, `bench set-config -g maintenance_mode 0`) and restart the bench (the script does this).
9. **Stop the bench.** It stops everything of that bench, so also the other sites' processes; say so in the report. `--keep-running` skips it.

### Known failure modes

| Symptom | Fix |
|---|---|
| `Duplicate entry ... for key 'PRIMARY'` on Module Def after a failed install | Re-run `install-app <app> --force` (the script does this). |
| `Redis ... Connection refused` on 11000/13000 | Start Redis (step 3); after a failed `new-site` answer `y` to roll back, then re-run. |
| `Repository not found` / GitHub password prompt | Auth problem (step 2). Never type a password into that prompt. |
| Browser "Updating ... 503" | Maintenance flag, see step 8. |

## Optional: restore the Cloud backup, slim the database

Never part of a full run; only when the user asks, and confirm first (AskUserQuestion). Same rules as `../vidira-site-setup/SKILL.md` ("Optional: restore a Frappe Cloud backup, slim the database") and `README.md` sections D and E, with `guin.localhost`:

```bash
python3 "$SKILL/scripts/setup_guin_site.py" --only restore --backup <file>-database.sql.gz --dry-run   # then without --dry-run, run by the user (password prompts), add --slim to also empty the log tables
python3 "$SKILL/scripts/setup_guin_site.py" --only slim --dry-run                                      # then --confirm after the user's OK
```

- The Guin backup contains exactly frappe, erpnext, payments, india_compliance, taraknath, pos_next (all in `apps.tsv`); warn if a newer backup expects an app that is not cloned. It is small (115 MB), the restore takes about 2 minutes.
- After a restore: migrate, Administrator password of the user's choice, `scheduler disable`, `mute_emails 1`, clear caches (the script does all of it). Never stop the bench while a restore runs.
- **Slim policy: never delete transactions or master data**, only the log/queue/history tables in `../vidira-site-setup/slim-tables.txt`.

## Final report to the user

- Bench path and Frappe version, a table of installed apps (name, version, branch) from `list-apps`.
- Anything skipped, retried (`--force`) or changed on their system.
- Which apps were reused from the bench vs newly cloned.
- Whether the bench / Redis were stopped and the ports (8000, 9000, 11000, 13000) are free.
- How to use it: `cd ~/frappe/bt && bench start`, then http://guin.localhost:8000, login `Administrator` with the password they set.
- Apps are only installed; their own settings and data still need configuring in the site.
