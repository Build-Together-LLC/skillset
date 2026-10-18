# Jira integration — link tickets in notes & comparison docs

Every Jira ID in a release should be a **live hyperlink** to its ticket, the same way the tracker
links its PR column.

## Site & projects
- **Base URL:** `https://buildtogether.atlassian.net` (config: `JIRA_BASE_URL`).
- **Browse URL (all you need to LINK):** `<base>/browse/<KEY>` — e.g.
  `https://buildtogether.atlassian.net/browse/VE-271`. Project-agnostic: it works for **any** key.
- **Account:** `aman@buildtogether.co.in` (the token owner; default `JIRA_EMAIL`, overridable).
- **Projects (confirmed via the API):**
  - **VE — Vidira ERP** (`vidira_group`): e.g. `VE-271`, `VE-277`, `VE-291`, `VE-98`.
  - **BT — Build together**: deployment/process tasks (e.g. BT-38, BT-44).
  - **VWA — Vidira Warehouse App**; **AA — AI Automations**.
- **GUIN ERPNext Phase 2 is NOT a separate project.** That work lives in **VE**, flagged `[Guin]`
  in the summary or under the epic **VE-113 "ERP16 Phase 2"** (e.g. VE-179 site creation, VE-180 DB
  migration, VE-181 rack check, VE-182, VE-261 POSNext/AutoRider). A few deployment/process tasks
  sit in **BT**. So a GUIN deploy's Jira keys are usually **VE-\*** (occasionally **BT-\***) — link
  them the same way; the browse URL is project-agnostic, so you never need to special-case GUIN.

## Linking (needs NO credentials)
```python
import sys
sys.path.insert(0, "<skill>/scripts")
from jira import jira_url, find_keys
from docbuilder import Link            # or use docbuilder.jira_url

find_keys("feat(VE-271): ... see VE-291")     # -> ["VE-271", "VE-291"]
Link("VE-271", jira_url("VE-271"))             # -> hyperlink token for body/bullet/table
```
Detect keys in branch names, PR titles/bodies, and commit messages with `find_keys(...)`. In a
table's Jira column, pass `Link(key, jira_url(key))` instead of the plain key. If a change has no
Jira ticket, keep the cell as plain text (`(no Jira)`), never a fabricated link.

## Validation / enrichment (needs the token — optional)
The token is ONLY for confirming a key exists, pulling its summary/status/type/project, or listing
projects. Read it from the environment — **never hardcode or commit it**:
```bash
export JIRA_BASE_URL="https://buildtogether.atlassian.net"
export JIRA_EMAIL="<atlassian-account-email>"     # the account that owns the token
export JIRA_API_TOKEN="<token>"                    # rotate if it ever leaks into chat/logs/a file
```
```python
from jira import get_issue, list_projects
get_issue("VE-271")     # {key, summary, status, type, project, labels, url} or None if the key is bogus
list_projects()         # [{key, name}, ...] -> confirm the GUIN Phase-2 project key vs VE
```
Use `get_issue` to (a) catch a mistyped key before it becomes a dead link, and (b) optionally enrich
a row (e.g. show the ticket's status/summary). Use `list_projects` once to record the GUIN project
key here. `scripts/jira.env.example` is a fill-in template; copy it to a **git-ignored** location and
`source` it (or export the three vars in your shell) — do not commit the filled version.

## Security
- The token is a live secret. Keep it in the environment or a git-ignored file only; never in a
  skill file, a generated doc, the tracker, a PR body, or a commit. If it appears in chat/logs,
  rotate it in Atlassian → Account → Security → API tokens.
- Linking never transmits the token anywhere (browse URLs are static). Only `get_issue` /
  `list_projects` send Basic auth to `buildtogether.atlassian.net`.
