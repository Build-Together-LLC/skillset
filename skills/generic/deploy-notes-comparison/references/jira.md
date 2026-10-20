# Jira integration — link tickets in notes & comparison docs

Every Jira ID in a release should be a **live hyperlink** to its ticket, the same way the tracker
links its PR column.

## Site & projects

- **Base URL:** from `JIRA_BASE_URL`, or the product config's ticket base. There is no default —
  the helper raises rather than guess a site.
- **Browse URL (all you need to LINK):** `<base>/browse/<KEY>` — e.g.
  `https://your-site.atlassian.net/browse/PROJ-271`. Project-agnostic: it works for **any** key,
  so you never special-case a project.
- **Account:** `JIRA_EMAIL` plus `JIRA_API_TOKEN`, both from the environment, and only for API
  calls. Linking needs neither.
- **Project keys** live in the product config. One product's work often spans several keys — a main
  delivery project plus a process/ops project — and a sub-programme usually is *not* its own
  project: it sits in the main one behind a label or an epic. Do not infer a key from a product
  name; read the config, or run `list_projects()` once and record what you find.

## Linking (needs NO credentials)
```python
import sys
sys.path.insert(0, "<skill>/scripts")
from jira import jira_url, find_keys
from docbuilder import Link            # or use docbuilder.jira_url

find_keys("feat(PROJ-271): ... see PROJ-291")     # -> ["PROJ-271", "PROJ-291"]
Link("PROJ-271", jira_url("PROJ-271"))             # -> hyperlink token for body/bullet/table
```
Detect keys in branch names, PR titles/bodies, and commit messages with `find_keys(...)`. In a
table's Jira column, pass `Link(key, jira_url(key))` instead of the plain key. If a change has no
Jira ticket, keep the cell as plain text (`(no Jira)`), never a fabricated link.

## Validation / enrichment (needs the token — optional)
The token is ONLY for confirming a key exists, pulling its summary/status/type/project, or listing
projects. Read it from the environment — **never hardcode or commit it**:
```bash
export JIRA_BASE_URL="https://your-site.atlassian.net"
export JIRA_EMAIL="<atlassian-account-email>"     # the account that owns the token
export JIRA_API_TOKEN="<token>"                    # rotate if it ever leaks into chat/logs/a file
```
```python
from jira import get_issue, list_projects
get_issue("PROJ-271")     # {key, summary, status, type, project, labels, url} or None if the key is bogus
list_projects()         # [{key, name}, ...] -> confirm which project a key belongs to
```
Use `get_issue` to (a) catch a mistyped key before it becomes a dead link, and (b) optionally enrich
a row (e.g. show the ticket's status/summary). Use `list_projects` once to record the project
key here. `scripts/jira.env.example` is a fill-in template; copy it to a **git-ignored** location and
`source` it (or export the three vars in your shell) — do not commit the filled version.

## Security
- The token is a live secret. Keep it in the environment or a git-ignored file only; never in a
  skill file, a generated doc, the tracker, a PR body, or a commit. If it appears in chat/logs,
  rotate it in Atlassian → Account → Security → API tokens.
- Linking never transmits the token anywhere (browse URLs are static). Only `get_issue` /
  `list_projects` send Basic auth to `your-site.atlassian.net`.
