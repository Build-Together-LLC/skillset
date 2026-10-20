---
name: frappe-system-console
description: >
  Writes paste-ready Frappe System Console scripts (Setup → System Console) for data
  audits, fixes, deletions, syncs and one-off migrations on any Frappe bench site, always with a
  `DRY_RUN = True / False` toggle so the user previews first and executes second. Scripts obey
  the safe_exec sandbox (no imports, no `.format()`, no getattr/open/eval, no raw write SQL, no
  `_`-prefixed names) and the house style (no `+=`, no walrus). The script is output in chat
  only — never saved as a file. Use for "system console script", "console script",
  "paste script", "dry run", "DRY_RUN", "data fix script", "dedupe/cleanup script",
  "bulk update/delete on staging", or "bench console one-liner" for Frappe Cloud/staging/prod.
---

# Frappe System Console Scripts

Write scripts the user **pastes into Setup → System Console → Run** (Type: Python; needs the
System Manager role). Output **only in the chat reply**. **Never** create or save a `.py` file
unless the user explicitly asks for a standalone bench script (see the exception below).

`frappe` and `print` are already in scope. **Do not add `import` / `from … import`.**

Every run is stored in **Console Log** with the full script text — never put passwords, tokens
or customer data in a script.

## What the sandbox allows (version-dependent — checked on two real versions)

Two sources: the constructs below were tested directly on Frappe **v15.113.4**, and a production
Console Log from a **Frappe v15.65.0** site was mined for what really ran (a Console Log row has
`committed = 1` only when the run raised no exception *and* Commit was ticked — 228 of 818
scripts). Constructs marked "never seen passing" are inferred from that log, not tested on
v15.65. The sandbox tightens between versions, so write to the
**intersection** — code that passes on both — unless the user says which site it is for.

**Fails on v15.113 (tested) and never seen passing on v15.65 — never write:**

| You write | Fails with | Use instead |
|---|---|---|
| `import x` / `from x import y` | `__import__ not found` | nothing — `frappe`, `frappe.utils`, `frappe.db` are in scope |
| `getattr`, `hasattr`, `dir`, `open`, `eval`, `exec` | `NameError` / `Eval calls are not allowed` | `x.get("k")`, `try/except`, `frappe.get_all` |
| any name starting with `_` (`frappe._dict`, `__name__`) | `invalid attribute name … starts with "_"` | plain dicts; `row.name` attribute access works on `get_all` rows |
| raw `UPDATE` / `DELETE` / `INSERT` in `frappe.db.sql` | `Read-Only queries are allowed` | `frappe.db.set_value`, `doc.db_set`, `frappe.delete_doc`, `doc.save()` |
| `frappe.db.delete`, `frappe.as_json`, `frappe.get_attr` | attribute error | `frappe.delete_doc(...)`; `print` the dict directly |
| `frappe.local.site` | prints `None` | `frappe.utils.get_url()` |

**Version-dependent — avoid:**

| You write | v15.65 | v15.113 |
|---|---|---|
| `"…{}…".format(x)` | ran | **fails** (`format is an unsafe attribute`) |

So use f-strings (`f"{x}"`) or `"%s" % x` — both pass everywhere (f-strings appear in 42 and
`%`-formatting in 20 of those 228 committed runs; `.format()` in just 1, from July).

**Passes on both — use freely:** `def` helpers (and closures over a list/dict), `lambda` as a
`sorted(key=…)`, `setdefault`, `try/except Exception as e`, tuple unpacking in `for a, b in …`,
`{**d}`, comprehensions, `sum(x for …)`, `while`, `or_filters`, `pluck`, `frappe.db.get_all`,
`frappe.get_meta(dt).has_field(f)`, `doc.db_set`, `doc.save()/.cancel()/.submit()`,
`insert(ignore_permissions=True)`, `frappe.db.sql(select…, (value,), as_dict=True)`.

**`log(...)`:** 96 of the author's 228 committed runs call `log("…")`, and 55 of the 818 scripts define
it themselves. It is a builtin on v15.113; it was not verified as a builtin on v15.65. So define
it once at the top and it works everywhere: `def log(msg):` then `    print(msg)`.

**Batch large jobs (the author's own pattern — 38 committed scripts use `BATCH_SIZE`):** when a job
touches thousands of rows or moves files, process `BATCH_SIZE` rows per run, print
`remaining after this run: N`, commit at the end of each run, and tell the user to re-run until it
reaches 0. Select the next batch with a filter that excludes already-processed rows so every run is
idempotent and resumable.

**House style (kept for consistency, not because the sandbox needs it):**

- Counters as `n = n + 1`, not `n += 1` — `+=` ran on both versions, but prefer the explicit form.
- No walrus `:=`.
- Keep the page-sized output readable: cap sample lists at 5–20 rows.

## The DRY_RUN contract (every script that writes)

1. `DRY_RUN = True` is the **first executable line** — the user flips it to `False` for step 2.
2. Reads and decisions happen in both modes; **every write sits only in the `else` / `if not DRY_RUN` branch**. The dry run prints `WOULD …` for exactly the rows the execute run will touch.
3. The banner prints `Mode: DRY-RUN` or `Mode: EXECUTE` and `frappe.utils.get_url()`.
4. The summary prints counts (`updated / skipped / errors`) and, in dry run, the next step.
5. **One** `frappe.db.commit()` at the very end, only `if not DRY_RUN and updated`.
6. Rows that don't fit a clear rule are **skipped and listed as `MANUAL REVIEW`**, never guessed.

**Commit semantics (tested through `System Console.run`):**

| Script calls `frappe.db.commit()` | Commit box | Result |
|---|---|---|
| no | unticked | everything **rolled back** |
| no | ticked | persisted |
| yes, at the end | either | persisted (the box is irrelevant) |
| yes, then an exception | ticked | **partial** write persists |
| exception *before* the final commit | ticked | all rolled back |

So: `DRY_RUN` is the only real gate (the checkbox does **not** stop a script-level commit).
Keep the commit last so any error before it undoes the whole run, and still tell the user to
tick **Commit** for the execute run. A read-only audit needs no toggle and no commit.

## Standard shape

```python
# System Console — [one-line purpose]
# Step 1: DRY_RUN = True  -> Run, read the output
# Step 2: DRY_RUN = False -> tick Commit, Run again

DRY_RUN = True

print("=" * 70)
print("[Title] | " + frappe.utils.get_url())
print("Mode:", "DRY-RUN" if DRY_RUN else "EXECUTE")
print("=" * 70)

rows = frappe.get_all("DocType", filters={...}, fields=["name", "..."])
print("candidates:", len(rows))

updated = 0
skipped = 0
errors = 0

for row in rows:
    if not_a_clear_case:
        skipped = skipped + 1
        print("MANUAL REVIEW", row.name)
        continue
    try:
        if DRY_RUN:
            print("WOULD  ", row.name)
        else:
            frappe.db.set_value("DocType", row.name, "field", value, update_modified=False)
            print("UPDATED", row.name)
        updated = updated + 1
    except Exception:
        errors = errors + 1
        print("ERROR  ", row.name, frappe.get_traceback().splitlines()[-1])

if not DRY_RUN and updated:
    frappe.db.commit()
    print("Committed.")

print("")
print("SUMMARY updated=%s skipped=%s errors=%s" % (updated, skipped, errors))
if DRY_RUN:
    print(">>> Review above, set DRY_RUN = False, tick Commit, Run again.")
print("=" * 70)
```

Ready-made, tested variants (audit, bulk update, resumable batch, guarded delete, field sync, dedupe, capped sample
print): [references/recipes.md](references/recipes.md). Start from one of those, then adapt.

## Write operations

- Bulk fixes: `frappe.db.set_value("DocType", name, "field", value, update_modified=False)` (also accepts a dict of fields). Prefer it over `doc.save()` unless validations/hooks must run.
- Deletes: `frappe.delete_doc("DocType", name, force=1, ignore_permissions=True)` — only when the user's intent is clear; first count links (`frappe.db.count("Child", {"parent_field": name})`) and print `MANUAL REVIEW` for linked rows.
- Before any delete or mass update print: total candidates, the keep/change rule in a header comment, and the first 5–10 sample rows.
- Re-read after writing when correctness matters (`frappe.db.get_value`) and print the counts.
- Never `frappe.db.sql` for writes; use it only for `SELECT` (grouped audits, `having`, joins). Always pass values with `%s` placeholders, not string concatenation.

## Read-only checks

- No toggle needed. Use `frappe.get_all` with explicit `fields`/`limit`, or `frappe.db.sql(..., as_dict=True)` for grouping.
- Print counts first, then a capped sample (`while` index loop below), then guidance on the next script.

```python
i = 0
while i < len(rows) and i < 5:
    print("  -", rows[i].name)
    i = i + 1
```

## Output format in chat

Always reply with:

1. **Where to run** — Setup → System Console → Type: Python (site name if relevant)
2. **Steps** — Run with `DRY_RUN = True` and review → set `DRY_RUN = False`, tick **Commit**, Run again
3. **The full script** in one fenced `python` block — copy-paste ready, nothing elided
4. **What to look for** — expected `WOULD …` lines, the SUMMARY counts, `MANUAL REVIEW` rows
5. **Caveats** — what the script does *not* cover, and how to roll back (usually: restore the backup; `set_value` fixes can be reverted by a reverse script — offer one)

**Do not** say "I created `migration/foo_console.py`". **Do not** use the Write tool for console scripts.

## Standalone bench scripts (exception)

Only if the user explicitly asks for a **file** runnable via `bench --site X console` or
`python migration/…py`:

- That file **may** use `import frappe`, `frappe.init(site=…)`, `frappe.connect()`, `frappe.db.sql` writes and `frappe.db.commit()`.
- Keep the same `DRY_RUN = True` toggle and summary block.
- Label it clearly: **"bench file"** vs **"System Console paste"**.

Default assumption: **System Console paste only**.

## Safety checklist before replying

- [ ] `DRY_RUN = True` is the default and the first assignment
- [ ] Every write is unreachable when `DRY_RUN` is true
- [ ] No imports, no `.format()`, no `getattr/open/eval`, no `_` names, no raw write SQL, no `+=`
- [ ] Banner uses `frappe.utils.get_url()`, not `frappe.local.site`
- [ ] Counts and sample rows are printed before anything destructive
- [ ] Unclear rows are skipped with `MANUAL REVIEW`
- [ ] One commit at the end, guarded by `not DRY_RUN`
- [ ] Reply states the rollback path and what to verify afterwards
- [ ] For migrate blockers, duplicate groups print `name`, `workflow_state` and the identifying fields (e.g. `school`, `academic_year`)

## Pair with other skills

| Need | Skill |
|---|---|
| Find existing DocTypes / avoid duplicate design | [frappe-solutioning](../frappe-solutioning/frappe-solutioning.md) |
| Permanent hook / override in an app | [frappe-developer](../frappe-developer/SKILL.md) |
| Whitelisted APIs, jobs, controllers | [server-scripts](../server-scripts/SKILL.md) |
| Investigating the error that needs the fix | [frappe-debug](../frappe-debug/SKILL.md) |
| One-off paste script for ops | **frappe-system-console** (this skill) |
