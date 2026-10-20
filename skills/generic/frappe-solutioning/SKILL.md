---
name: frappe-solutioning
description: >
  Use BEFORE designing or building any new Frappe/ERPNext feature, DocType, workflow or API.
  Searches the bench — upstream apps and custom apps alike — so nothing is built that already
  exists, and reports what to reuse, what to extend and what genuinely has to be new. TRIGGER
  when the user says "build", "add", "create", "design" or "implement" anything in
  Frappe/ERPNext, before any code is written.
---

# Frappe Solutioning

Before designing anything, find out what is already there. ERPNext ships roughly a thousand
DocTypes and most benches carry a dozen custom apps on top; the common failure is building a
second version of something that exists two apps over.

Search first, report, then design. Do not write code in this phase.

## Step 1 — Establish the search surface

```bash
ls apps/                       # every app on the bench
cat sites/apps.txt             # the ones actually installed
```

Split them into **upstream** (frappe, erpnext, hrms, payments, lms, india_compliance, …) — search
these but never modify them — and **custom** apps, which are yours to extend.

## Step 2 — Find existing DocTypes

A DocType's definition is `<app>/<module>/doctype/<snake_name>/<snake_name>.json`.

```bash
# by name, fuzzy
find apps -path '*/doctype/*' -name '*.json' | grep -i '<keyword>'

# by label or field, when the name does not match the domain language
grep -rl '"label": "<Thing>"' apps --include='*.json' | grep '/doctype/'
grep -rl '"fieldname": "<field>"' apps --include='*.json' | grep '/doctype/'
```

Read the ones that look close: field list, `is_submittable`, `istable`, naming series, permissions.
A DocType that is 80% right is an extend candidate, not a reason to build a new one.

## Step 3 — Find existing workflows and server logic

```bash
find apps -path '*/workflow/*' -name '*.json'              # Workflow definitions
grep -rn 'doc_events' apps/*/*/hooks.py                     # what already hooks the doctype
grep -rn '@frappe.whitelist' apps --include='*.py' | grep -i '<domain>'
```

Workflows are also created at runtime, so check the site as well as the code:

```bash
bench --site <site> console
>>> frappe.get_all("Workflow", fields=["name", "document_type", "is_active"])
```

## Step 4 — Measure the blast radius before proposing a change

For any shared DocType you intend to touch, count what depends on it:

```bash
grep -rn '"<DocType Name>"' apps --include='*.py' --include='*.js' --include='*.json' | wc -l
grep -rn '"options": "<DocType Name>"' apps --include='*.json'   # Link fields pointing at it
```

A change to something with a hundred references is a different proposal from one with three. Say
the number in the report; do not leave the reader to guess.

## Step 5 — Report before recommending

Produce this before suggesting anything new:

```
## Solutioning Report: <Feature>

### Existing DocTypes (reuse candidates)
| DocType | App | Module | Why it is close | Blast radius |
|---------|-----|--------|-----------------|--------------|

### Existing workflows
| Workflow | Document Type | App | States | Active |
|----------|---------------|-----|--------|--------|

### Existing APIs and hooks
| Function | File | App | What it already does |
|----------|------|-----|----------------------|

### Recommendation
- REUSE:      what works as-is, and how to call it
- EXTEND:     what to add custom fields or states to, and which app owns it
- BUILD NEW:  only what genuinely does not exist, with the gap stated
- RISKS:      shared DocTypes with a wide blast radius; anything semantically
              close enough to confuse users later
```

## Rules

- Never propose a DocType that already exists in any app on the bench.
- Close but not exact → extend with Custom Fields or a child table, do not fork.
- A workflow exists for that document type → reuse it and add states.
- Always name the app and the file where existing code lives. "ERPNext has something like this"
  is not a finding; a path is.
- Search upstream apps too. Most of what people plan to build is already in ERPNext.
- Measure blast radius before recommending a change to anything shared.
- If the search genuinely turns up nothing, say so explicitly — that is a finding, not a gap in
  the report.
