---
name: graphify
description: Use when you need the INTERNALS of a Unity/Walnut Frappe app — which functions/classes/whitelisted APIs exist, which controller governs a DocType, what hooks.py wires up, or which function calls which inside an app. This is the symbol-level ("zoom in") companion to /depmap (which covers cross-app coupling). Invoke when locating an existing API before writing a new one, tracing a call path, checking a DocType's controller, or understanding an app's internal structure during BRD/PRD/LLD work.
---

# Graphify — Symbol-Level Knowledge Graph

Graphify answers *"what is inside an app and how do its pieces connect"*. It is
the zoom-in layer; **[/depmap](../depmap/SKILL.md) is the zoom-out layer** (which
app depends on which). Reach for graphify when the question is about functions,
classes, whitelisted APIs, DocType controllers, hooks wiring, or intra-app call
paths — and for cross-app coupling, use depmap.

## FIRST STEP — get the freshest graph

If a central fetch server is configured, refresh first:

```bash
bash ~/frappe-bench/apps/unity_dev_tools/scripts/graphify/sync.sh 2>/dev/null || true
```

Then confirm freshness by reading `MANIFEST.json` (below). If the sync script
isn't present or fails (no server/network), fall back to the committed JSON on
disk and tell the user the data may be stale. The graph is regenerated every 12 hours by
the `merge_master` cron on the VPS, right after depmap.

## Files (always at these paths)

- `~/frappe-bench/apps/unity_dev_tools/dev_memory/graphify/MANIFEST.json` — generation timestamp + totals. **Read first** to confirm freshness.
- `~/frappe-bench/apps/unity_dev_tools/dev_memory/graphify/graph.json` — overview: every app's branch list + per-app symbol/edge counts.
- `~/frappe-bench/apps/unity_dev_tools/dev_memory/graphify/apps/<app>.json` — per-app detail, keyed by branch. Each branch has:
  - `whitelist_apis` — `{function, signature, doc, file, lineno}` (module functions and whitelisted methods as `Class.method`)
  - `controllers` — DocType controller classes: `{class, bases, file, lineno, methods[]}`
  - `hooks` — parsed `hooks.py` wiring: `doc_events`, `scheduler_events`, `override_doctype_class`, `override_whitelisted_methods`, `fixtures`, `website_route_rules`, …
  - `call_edges` — intra-app `{from: "Class.method"|"func", to: "callee", count}`
  - `js_call_targets` — `frappe.call('<method>')` strings found in JS/Vue
  - `modules` — per-module `{function_count, class_count, api_count, file_count}`
- `~/frappe-bench/apps/unity_dev_tools/dev_memory/graphify/GRAPH_REPORT.md` — human digest.

Use `grep` to locate and `python3 -c` to read structured values. **Do not use
`jq`** — it is not installed on the index host and may be absent on a dev
laptop; `python3` ships with every Frappe bench. `MANIFEST.json` carries
`schema_version` (currently 2) — if it differs, say the skill is out of date
rather than guessing at paths. Only `Read` the full per-app
file when you need the complete symbol list.

## How to use during planning / coding work

1. **"Is there already an API for X?"** — before writing a new whitelisted
   endpoint, grep `apps/<app>.json` (or all `apps/*.json`) for the concept in
   `whitelist_apis[].function` / `.doc`. Reuse beats reinvention.
2. **"Which controller governs DocType Y?"** — look in `apps/<app>.json` →
   `controllers[]` for a class whose `file` sits under `.../doctype/y/`, or grep
   for the class name. Its `methods[]` list is the lifecycle surface
   (`validate`, `on_submit`, …).
3. **"What does hooks.py wire for this app?"** — read `apps/<app>.json.hooks`.
   `doc_events` tells you what fires on DocType events; `override_doctype_class`
   tells you which core DocTypes the app replaces; `scheduler_events` lists cron
   jobs.
4. **"Who calls this function?"** — grep `call_edges[]` for `"to": "<name>"` to
   find callers within the app (blast radius of a change). For *cross-app*
   callers, switch to /depmap's `import` / `api_call` edges.
5. **"What's the internal shape of this app?"** — `modules` gives the module
   breakdown; the per-app counts in `graph.json` give a one-line size estimate.

## Output block for BRDs/PRDs/LLDs

```markdown
### Symbol-level snapshot — <app>

**Relevant existing APIs:**
- `<function><signature>` — <doc> (`<file>`)

**Controller(s) in play:**
- `<Class>` (bases: <bases>) → methods: <validate, on_submit, …> (`<file>`)

**Hooks that will fire:**
- doc_events: <DocType> → <handler>
- scheduler_events: <cron entries>

**Internal blast radius:**
- <N> intra-app callers of `<function>` (from call_edges)
- For cross-app impact, see the /depmap snapshot
```

## When to proactively invoke

| Trigger | Why |
|---|---|
| About to add a whitelisted API / util function | Check `whitelist_apis` first — it may already exist |
| Need to know a DocType's lifecycle hooks | `controllers[].methods` + `hooks.doc_events` are the answer |
| Tracing a call path inside an app | `call_edges` gives caller→callee within the app |
| "What does this app expose / override?" | `whitelist_apis` + `hooks.override_*` |
| Estimating a refactor's internal churn | Count inbound `call_edges` for the symbol |

## Relationship to the other indexes

- **/depmap** — cross-app edges (DocType links, Python imports, `frappe.call`).
  Use for "what breaks in *other* apps if I change this."
- **contextplus-master.json** — org-wide DocType/workflow/API fingerprint +
  developer ownership. Use for "who owns this / where does this concept live."
- **graphify (this)** — per-app symbol graph + intra-app call edges. Use for
  "what's inside this app and how do its pieces connect."

## Limitations

- Python symbols are AST-accurate; JS/Vue is a light regex scan (function names +
  `frappe.call` targets only).
- `call_edges` are name-resolved within a single app — a call resolves to any
  same-named symbol defined in that app, so overloaded/duplicated names may be
  slightly over-linked. Cross-app calls are intentionally out of scope (use depmap).
- `hooks` captures only literal (constant) values; dynamically-built hook dicts
  show as `"<dynamic>"`.
- Coverage is whatever `tracked_repos.yml` cloned into `source_clones/`; an app
  missing there is missing here.
