---
name: depmap
description: Use when planning features, writing BRDs/PRDs/LLDs, deciding where new code belongs, or reasoning about cross-app dependencies in the Unity Frappe bench (apps under ~/frappe-bench/apps/). Provides on-demand inspection of which apps/modules/DocTypes/functions depend on which others, sourced from the dependency map rebuilt every 12 hours. Invoke whenever the user mentions a Unity app by name, asks "what would change if we touch X", or starts scoping a feature that may cross app boundaries.
---

# Depmap — Cross-App Dependency Lookup

## FIRST STEP — sync the latest depmap

Before answering any dependency question, run:

```bash
bash ~/frappe-bench/apps/unity_dev_tools/scripts/depmap/sync.sh
```

This fetches the latest tarball from the central depmap server (auth via key in `scripts/depmap/server.conf`, which is committed to the private repo). It overwrites `dev_memory/depmap/` with the freshest data — rebuilt every 12 hours by the cron. If `sync.sh` fails (server down, no network), fall back to whatever JSONs are currently on disk and tell the user the data may be stale.

If `sync.sh` reports a manifest timestamp older than ~13 hours, mention it — the build runs every 12h, so anything past one missed cycle means the cron has failed.

## What this is

A pre-computed map of cross-app dependencies in the Unity Frappe bench (~50 apps), regenerated every 12 hours by the `merge_master` cron. Three edge types are tracked:

| Type      | Source                                                  | Strength |
|-----------|---------------------------------------------------------|----------|
| `link`    | DocType A's Link/Table field points to DocType B        | Strong — schema coupling |
| `import`  | Python file does `from <app> import ...`                | Strong — code coupling |
| `api_call`| JS/Vue file does `frappe.call('<app>.<module>.<func>')` | Fragile — string-typed |

## Files (always at these absolute paths)

- `~/frappe-bench/apps/unity_dev_tools/dev_memory/depmap/MANIFEST.json` — `schema_version`, generation timestamp, edge counts, coverage totals. **Read first** to confirm freshness.
- `~/frappe-bench/apps/unity_dev_tools/dev_memory/depmap/depmap.json` — overview: full app list, per-app summary (doctype/controller/api counts, modules), and aggregated cross-app edges with sample evidence.
- `~/frappe-bench/apps/unity_dev_tools/dev_memory/depmap/apps/<app>.json` — per-app detail, **keyed by branch** (see schema below).
- `~/frappe-bench/apps/unity_dev_tools/dev_memory/depmap/COVERAGE.json` — every cloned (repo, branch) pair with status `indexed` / `skipped_not_frappe` / `failed`. Check this before claiming an app has no dependencies — it may simply have failed to index.
- `~/frappe-bench/apps/unity_dev_tools/dev_memory/depmap/index.html` — interactive D3 viewer for **humans** in a browser. Never read this file: it is ~5 MB of embedded data and tells you nothing the JSON doesn't.

## Schema — READ THIS BEFORE WRITING ANY LOOKUP

`MANIFEST.json` carries `"schema_version"`. **This skill is written for `schema_version: 2`.**
If the file reports a different version, stop and tell the user the skill is out of
date rather than guessing at paths — a silent mismatch returns empty results that
look like "no dependencies", which is the most dangerous wrong answer this index
can give.

Version 2 nests everything under `branches`, because one app can be indexed on
several branches at once (`develop` and `feature/x`):

```jsonc
// apps/<app>.json
{
  "app": "unity_gymkhana",
  "generated_at": "2026-09-02T…",
  "branches": {
    "feature/phase1-sports-booking": {
      "repo": "unity_gymkhana",
      "modules": { "<Module>": { "doctypes": [...], "apis": [...] } },
      "outbound_edges": [ {"type","from_app","from_branch","to_app","to_branch","from_dt","to_dt","field"} ],
      "inbound_edges":  [ ... ]
    }
  }
}
```

So the paths are `branches.<branch>.outbound_edges[]`, **not** `outbound_edges[]`.
A pre-2 flat file (edges at the top level) is stale data left over from before
2026-09-02 — treat it as untrustworthy and say so.

## How to use during planning work

When the user mentions an app, DocType, function, or starts a BRD/PRD/LLD:

1. **Confirm freshness and schema**: after `sync.sh` runs, read `MANIFEST.json` — check `schema_version` is 2, and that `generated_at` is within ~13h. The index rebuilds **every 12 hours**, not hourly — so up to half a day of lag is expected and fine, but older than ~13h means the cron has failed; say so before relying on the data.
2. **For an app-level question**: read `apps/<app_name>.json`, then for each branch in `branches`:
   - `branches.<branch>.outbound_edges` — what this app depends on (breaks if those apps change)
   - `branches.<branch>.inbound_edges` — what depends on this app (breaks if you change here)
   - `branches.<branch>.modules.<mod>.{doctypes, apis}` — what's inside the app
   If an app has several branches, **say which branch you are quoting.** A feature branch and `develop` can disagree, and an LLD that silently mixes them is wrong.
3. **For a DocType-level question**: search `apps/*.json` for the DocType name — as `modules.*.doctypes[].name` to find its owner, or as `to_dt` to find references to it.
4. **For a function/API question**: search `apps/*.json` for the function name in `modules.*.apis[]`.

**Use `grep` for locating, `python3` for structured reads.** `jq` is *not* installed
on the index host and may be missing on a dev laptop; `python3` ships with every
Frappe bench. Cheap patterns:

```bash
D=~/frappe-bench/apps/unity_dev_tools/dev_memory/depmap

# Which apps reference the DocType "Student"?
grep -l '"to_dt": "Student"' $D/apps/*.json

# Blast radius of one app, per branch:
python3 -c "
import json;d=json.load(open('$D/apps/unity_gymkhana.json'))
for b,v in d['branches'].items():
    print(b, 'out=',len(v['outbound_edges']), 'in=',len(v['inbound_edges']))"

# Who depends on this app, grouped by app (the 'what breaks' answer):
python3 -c "
import json,collections;d=json.load(open('$D/apps/education.json'))
c=collections.Counter(e['from_app'] for v in d['branches'].values() for e in v['inbound_edges'])
print(c.most_common(15))"
```

Only `Read` a full per-app file when you genuinely need every edge — they run to
hundreds of KB.

## Output format for BRDs/PRDs/LLDs

Embed dependency findings in planning docs using this structure so reviewers can scan risk quickly:

```markdown
### Cross-app dependency snapshot — <app|doctype|feature>

**Depends on (outbound):**
- `<target_app>` — N edges (M link, K import, J api_call)
  - e.g. `<source_dt>.<field> → <target_dt>`

**Depended on by (inbound):**
- `<source_app>` — N edges (...)

**Risk callouts:**
- <inbound_count> inbound edges → blast radius is <small|moderate|wide>
- Linked DocTypes in <other_app> imply schema coupling — coordinate migrations
- N JS api_call references → string-typed, brittle on rename
```

## When to proactively invoke this skill

| Trigger                                              | Why                                                        |
|------------------------------------------------------|------------------------------------------------------------|
| User mentions a Unity app by name in design context  | Anchor the discussion in real coupling, not assumed coupling |
| Writing a BRD/PRD that touches >1 app                | Surface cross-app risks before they become rework         |
| Designing a new DocType                              | Decide which app it belongs to based on existing edges    |
| Estimating refactor effort                           | Inbound edge count ≈ blast radius                         |
| Reviewing a "should X live in app A or app B" choice | Edge counts settle the argument with evidence             |
| User asks "what breaks if we change X"               | Inbound edges to X are exactly the answer                 |

## Concrete workflow examples

### Example 1 — "Add a Hostel Visitor Pass DocType"

1. Read `apps/hostel_management.json` and `apps/visitor_management.json`
2. Look at outbound_edges in each: does either already link to the other?
3. Recommend the app whose existing modules align (if hostel_management already imports from visitor_management → put it in hostel_management with a Link field; if neither links → propose visitor_management as owner since "Visitor" is its core entity)

### Example 2 — "Renaming Student field on Program Enrollment"

1. Grep `apps/*.json` for `"to_dt": "Program Enrollment"` to find every app whose DocType links to it
2. List affected apps + sample fields in the LLD
3. Mark the migration as cross-app and require coordination

### Example 3 — "Is unity_gymkhana safe to extract into its own bench?"

1. Read `apps/unity_gymkhana.json`
2. Sum outbound edges by target app — anything pointing at non-frappe/erpnext apps is a coupling that needs decoupling first
3. Surface the list as the prerequisite work

## Refresh paths

**Standard (any dev):** `bash ~/frappe-bench/apps/unity_dev_tools/scripts/depmap/sync.sh` — pulls the latest tarball from the central server. Use this — it's what the `## FIRST STEP` block at the top tells Claude to do.

**VPS admin only:** `python3 ~/frappe-bench/apps/unity_dev_tools/scripts/depmap/build_depmap.py` — regenerates from scratch by scanning the local bench. Only useful on the machine that runs the cron, since most dev workstations don't have every app cloned.

## Limitations

- Coverage is every non-archived repo in `UnityAppSuite` + `WalnutAppSuite` on its default branch, plus tracked feature branches and pinned upstream forks — currently ~82 apps across ~87 (app, branch) pairs, scanned from `source_clones/`, not from the local bench. Repos in the `exclude:` block of `tracked_repos.yml` are deliberately out (not Frappe apps, or excluded by request); empty repos with no default branch cannot be cloned. `COVERAGE.json` lists the status of every pair.
- Python import scan captures only top-level package imports; aliased and dynamic imports are missed. **Absence of an import edge is weak evidence** — do not conclude "nothing depends on this" from the index alone.
- JS scan only catches literal `frappe.call('<app>.<...>')` patterns — method names built at runtime are invisible.
- `inbound_edges` are populated for far fewer apps than `outbound_edges` (most leaf apps genuinely have no dependents). A low inbound count on a *platform* app is more likely a scan gap than a real absence — sanity-check before quoting it as blast radius in an LLD.
- Module names appear in both Title Case (from DocType `module` field) and snake_case (from file paths). Treat them as the same when reasoning.
- The index answers *who touches what*. It does not know whether the coupling is correct, intentional, or safe — that still needs reading the code.
