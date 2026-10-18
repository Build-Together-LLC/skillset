# Product config — VIDIRA and GUIN

Two products share this skill. Detect which (Step 0 of SKILL.md), then use its block below.
Branches/repos are config: they can change later (e.g. GUIN may re-point off `develop`/`BT`).

---

## VIDIRA

| Key | Value |
|---|---|
| App / repo | `Vidira-Innovations/vidira_group` (ERPNext v16 custom app) |
| Local clone | `/home/aman/personal/buildtogether/apps/vidira_group` |
| Flow | Develop → UAT → Prod. Release = `Prod ← UAT [DD-MM-YYYY]` PR (base `prod`, head `uat`); promotion = `UAT ← Develop [DD-MM-YYYY]`. Feature PRs land on `develop`. |
| Release signal | the Prod ← UAT promotion PR (or in-flight UAT ← Develop head) |
| Docs folder | `/home/aman/personal/buildtogether/docs/vidira/prod deployment/` |
| Doc filename | `N. YYYY-MM-DD _ Prod Deployment - Detailed Notes .docx` |
| Doc title | `Vidira Group — Prod Deployment: Detailed Notes` |
| Tracker | single `*.xlsx` in the docs folder (newest; don't hardcode) |
| Required input | the prod PR number (flag + ask if missing) |
| PR link base | `https://github.com/Vidira-Innovations/vidira_group/pull/<n>` (commit: `/commit/<sha>`) |
| Mode 2 candidate | `develop` tip vs current `upstream/prod` — or a shared Prod PR head vs prod |
| Jira | `https://buildtogether.atlassian.net`, project key **VE** (e.g. VE-271, VE-277, VE-291). Link via `jira_url(key)`; see `references/jira.md`. |
| Note | `gh pr edit` fails here (Projects-classic); set PR bodies via `gh api --method PATCH repos/Vidira-Innovations/vidira_group/pulls/<n> -F body=@file` |

Tracker schema — **16 columns, no App column** (unchanged from the original series):
`Customization, Type, Origin (vs v15), Port notes (enhanced / new), Description, Jira ID, PR(s),
Prod Deployment Date, Build, Development, Testing, Is Deployed, Current Status, Verified by Vidira,
Notes / mapping, Hours Spent (Jira)`  → `status_col = 13`, `ncols = 16`.
`All PRs`: `check | PR # | Title | Jira / Branch | Merged | Prod Deployment | Feature | Status | Link | Hours`.
`Deployments`: `# | Prod Deployment Date | Build commit | Doc | Scope (commit range) | Key contents | Hours`.

---

## GUIN  (guinerp.m.frappe.cloud)

| Key | Value |
|---|---|
| Site | `guinerp.m.frappe.cloud` (Frappe Cloud, Vidira Application / Retailers). Created 20 Jul 2026. |
| Tracked apps | **Taraknath** = `Vidira-Innovations/taraknath` @ `develop`; **POSNext** = `Build-Together-LLC/POSNext` @ `BT`. (Stock v16 apps — frappe, erpnext, india_compliance, payments — are NOT tracked.) |
| Local clones | taraknath: `/home/aman/personal/buildtogether/apps/taraknath`; pos_next: (clone if needed) |
| Flow | **No prod branch / promotion PR.** A release = the commit delta on each branch between two Frappe-Cloud deploys. |
| Release signal | Frappe-Cloud **Update Site Pull / Update Site Migrate** jobs (Migrations/Jobs tab), grouped by day. Convert "X days ago" to an absolute date. |
| Build commit | per app, from the site's **Apps** tab (Commit column) at each deploy, or the branch tip. |
| Docs folder | `/home/aman/personal/buildtogether/docs/guin/Deployment Notes/` |
| Doc filename | `N. YYYY-MM-DD _ GUIN Deployment - Detailed Notes .docx` |
| Doc title | `GUIN (guinerp) — Site Deployment: Detailed Notes` |
| Tracker | single `*.xlsx` in the docs folder — `GUIN - Feature x PR x Date Map - DD-MM-YYYY.xlsx` |
| Required input | BOTH repos always; per-app previous build commit + deploy date (flag + ask if missing) |
| Baseline (D1) | Go-live window 20–26 Jul 2026. Taraknath #3–#50 + direct commits `bd84bc3`,`796d49c`,`5ddbff8` (tip `5ddbff8`); POSNext #1–#20 (tip = 26 Jul BT commit). |
| PR link base | Taraknath `https://github.com/Vidira-Innovations/taraknath/pull/<n>`; POSNext `https://github.com/Build-Together-LLC/POSNext/pull/<n>` (commit: `/commit/<sha>`) |
| Mode 2 candidate | per app: taraknath `develop` vs last-deployed commit; pos_next `BT` vs last-deployed commit (user shares prev/target commits or two Frappe-Cloud Apps snapshots) |
| Jira | Same site `https://buildtogether.atlassian.net`. GUIN work is in **VE** (tagged `[Guin]` / epic **VE-113 "ERP16 Phase 2"**), a few tasks in **BT** — no separate GUIN project. Link via `jira_url(key)`. |

Tracker schema — **15 columns, WITH `App`** → `status_col = 12`, `ncols = 15`:

`Deployment Map` / dated sheets:
| # | Column | Notes |
|---|---|---|
| 1 | Change | short feature/fix name |
| 2 | **App** | `Taraknath` or `POSNext` |
| 3 | Type | Feature / Enhancement / Bug / Change |
| 4 | Description | business-level |
| 5 | Jira ID | e.g. VE-128, or `(no Jira)` |
| 6 | PR(s) / Commit | `#13, #15` or a short sha for direct commits |
| 7 | Deployment # | `1`, `2`, … |
| 8 | Deployment Date | `YYYY-MM-DD` |
| 9 | Build | target build commit (short sha, that app) |
| 10 | Branch | `develop` / `BT` |
| 11 | Is Deployed | Yes / Yes (flag-gated) / Reverted / No |
| 12 | Current Status | free text; cell fill green/red/yellow |
| 13 | Verified | Yes / None |
| 14 | Notes / mapping | guards, flags, revert/walk-back history |
| 15 | Hours (Jira) | usually None |

`All PRs (task list)` — 11 cols:
`check | App | PR # | Title | Jira / Branch | Merged | Deployment Date | Deployment # | Feature | Status | Link`

`Deployments` — 8 cols:
`# | Deployment Date | Apps updated | Taraknath build | POSNext build | Scope (per-app ranges) | Doc | Key contents (net, excludes reverted)`

`Pending (not deployed)` — work merged to a branch but not yet on the site (e.g. taraknath **#51**,
merged 14 Aug, after the last deploy → "Update Available").

**Status fills:** green `FFC6EFCE` (deployed & working), red `FFFFC7CE` (reverted / not live),
yellow `FFEA9999` (paused / in progress).
