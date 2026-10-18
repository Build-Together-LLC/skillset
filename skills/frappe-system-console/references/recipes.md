# System Console recipes

Tested on Frappe v15.113.4 through `System Console.run` (dry run changes nothing; execute
persists; a delete with links is skipped). Each recipe has a **CONFIG** block — edit only that,
keep the rest. Variables are plain assignments so they stay inside the sandbox rules in `SKILL.md`.

## 1. Audit: find duplicates (read-only, no toggle)

```python
# System Console — find duplicate values of one field (read-only)
DOCTYPE = "ToDo"
FIELD = "description"
FILTERS = {"status": "Open"}          # {} for all rows
SHOW_GROUPS = 10

print("=" * 70)
print("Duplicate audit |", DOCTYPE, ".", FIELD, "|", frappe.utils.get_url())
print("=" * 70)

rows = frappe.get_all(DOCTYPE, filters=FILTERS, fields=["name", FIELD, "creation"], order_by="creation asc")
groups = {}
for r in rows:
    value = r.get(FIELD)
    if not value:
        continue
    if value not in groups:
        groups[value] = []
    groups[value].append(r.name)

dupes = []
for value in groups:
    if len(groups[value]) > 1:
        dupes.append(value)

print("rows scanned:", len(rows))
print("duplicate groups:", len(dupes))
i = 0
while i < len(dupes) and i < SHOW_GROUPS:
    print("  -", dupes[i], "x", len(groups[dupes[i]]), groups[dupes[i]][:5])
    i = i + 1
if len(dupes) > SHOW_GROUPS:
    print("  ... %s more groups" % (len(dupes) - SHOW_GROUPS))
print("=" * 70)
```

## 2. Bulk update one field (DRY_RUN)

```python
# System Console — set FIELD = NEW_VALUE on rows matching FILTERS
# Step 1: DRY_RUN = True  -> Run, review
# Step 2: DRY_RUN = False -> tick Commit, Run again

DRY_RUN = True
DOCTYPE = "ToDo"
FILTERS = {"status": "Open", "description": ["like", "legacy-%"]}
FIELD = "status"
NEW_VALUE = "Cancelled"

print("=" * 70)
print("Bulk update |", DOCTYPE, ".", FIELD, "->", NEW_VALUE, "|", frappe.utils.get_url())
print("Mode:", "DRY-RUN" if DRY_RUN else "EXECUTE")
print("=" * 70)

rows = frappe.get_all(DOCTYPE, filters=FILTERS, fields=["name", FIELD])
print("candidates:", len(rows))

updated = 0
skipped = 0
errors = 0
for row in rows:
    if row.get(FIELD) == NEW_VALUE:
        skipped = skipped + 1
        continue
    try:
        if DRY_RUN:
            print("WOULD   ", row.name, ":", row.get(FIELD), "->", NEW_VALUE)
        else:
            frappe.db.set_value(DOCTYPE, row.name, FIELD, NEW_VALUE, update_modified=False)
            print("UPDATED ", row.name)
        updated = updated + 1
    except Exception:
        errors = errors + 1
        print("ERROR   ", row.name, frappe.get_traceback().splitlines()[-1])

if not DRY_RUN and updated:
    frappe.db.commit()
    print("Committed.")

print("")
print("SUMMARY updated=%s skipped=%s errors=%s" % (updated, skipped, errors))
if DRY_RUN:
    print(">>> Review above, set DRY_RUN = False, tick Commit, Run again.")
print("=" * 70)
```

## 3. Sync field A → B (DRY_RUN)

```python
# System Console — copy SOURCE into TARGET where TARGET is empty
# Step 1: DRY_RUN = True  -> Run, review
# Step 2: DRY_RUN = False -> tick Commit, Run again

DRY_RUN = True
DOCTYPE = "ToDo"
SOURCE = "description"
TARGET = "reference_name"
FILTERS = {"description": ["like", "sync-%"]}

print("=" * 70)
print("Sync |", DOCTYPE, SOURCE, "->", TARGET, "|", frappe.utils.get_url())
print("Mode:", "DRY-RUN" if DRY_RUN else "EXECUTE")
print("=" * 70)

rows = frappe.get_all(DOCTYPE, filters=FILTERS, fields=["name", SOURCE, TARGET])
updated = 0
skipped = 0
for row in rows:
    if not row.get(SOURCE) or row.get(TARGET):
        skipped = skipped + 1
        continue
    if DRY_RUN:
        print("WOULD   ", row.name, ":", row.get(SOURCE))
    else:
        frappe.db.set_value(DOCTYPE, row.name, TARGET, row.get(SOURCE), update_modified=False)
        print("UPDATED ", row.name)
    updated = updated + 1

if not DRY_RUN and updated:
    frappe.db.commit()
    print("Committed.")

print("")
print("SUMMARY candidates=%s updated=%s skipped=%s" % (len(rows), updated, skipped))
if DRY_RUN:
    print(">>> Review above, set DRY_RUN = False, tick Commit, Run again.")
print("=" * 70)
```

## 4. Guarded delete: skip rows that have links (DRY_RUN)

```python
# System Console — delete rows matching FILTERS unless something links to them
# Step 1: DRY_RUN = True  -> Run, review (MANUAL REVIEW rows are never deleted)
# Step 2: DRY_RUN = False -> tick Commit, Run again

DRY_RUN = True
DOCTYPE = "ToDo"
FILTERS = {"description": ["like", "zz-delete-%"]}
# every place that can point at a row: (linked doctype, field holding the name)
LINKS = [["Communication", "reference_name"], ["Comment", "reference_name"]]

print("=" * 70)
print("Delete |", DOCTYPE, "|", frappe.utils.get_url())
print("Mode:", "DRY-RUN" if DRY_RUN else "EXECUTE")
print("=" * 70)

rows = frappe.get_all(DOCTYPE, filters=FILTERS, fields=["name"])
print("candidates:", len(rows))

deleted = 0
review = 0
errors = 0
for row in rows:
    blocked = 0
    for link in LINKS:
        blocked = blocked + frappe.db.count(link[0], {link[1]: row.name})
    if blocked:
        review = review + 1
        print("MANUAL REVIEW", row.name, "has", blocked, "linked rows")
        continue
    try:
        if DRY_RUN:
            print("WOULD DELETE", row.name)
        else:
            frappe.delete_doc(DOCTYPE, row.name, force=1, ignore_permissions=True)
            print("DELETED     ", row.name)
        deleted = deleted + 1
    except Exception:
        errors = errors + 1
        print("ERROR       ", row.name, frappe.get_traceback().splitlines()[-1])

if not DRY_RUN and deleted:
    frappe.db.commit()
    print("Committed.")

print("")
print("SUMMARY deleted=%s manual_review=%s errors=%s" % (deleted, review, errors))
if DRY_RUN:
    print(">>> Review above, set DRY_RUN = False, tick Commit, Run again.")
print("=" * 70)
```

## 5. De-duplicate: keep the oldest, delete the rest (DRY_RUN)

```python
# System Console — within each duplicate group keep the OLDEST row, delete the others
# Step 1: DRY_RUN = True  -> Run, review the KEEP / WOULD DELETE pairs
# Step 2: DRY_RUN = False -> tick Commit, Run again

DRY_RUN = True
DOCTYPE = "ToDo"
KEY_FIELD = "description"
FILTERS = {"description": ["like", "zz-dedupe-%"]}

print("=" * 70)
print("De-duplicate |", DOCTYPE, "by", KEY_FIELD, "|", frappe.utils.get_url())
print("Mode:", "DRY-RUN" if DRY_RUN else "EXECUTE")
print("=" * 70)

rows = frappe.get_all(DOCTYPE, filters=FILTERS, fields=["name", KEY_FIELD, "creation"], order_by="creation asc, name asc")
groups = {}
for r in rows:
    value = r.get(KEY_FIELD)
    if not value:
        continue
    if value not in groups:
        groups[value] = []
    groups[value].append(r.name)

deleted = 0
kept = 0
errors = 0
for value in groups:
    names = groups[value]
    if len(names) < 2:
        continue
    kept = kept + 1
    print("KEEP  ", names[0], "|", value)
    for name in names[1:]:
        try:
            if DRY_RUN:
                print("  WOULD DELETE", name)
            else:
                frappe.delete_doc(DOCTYPE, name, force=1, ignore_permissions=True)
                print("  DELETED     ", name)
            deleted = deleted + 1
        except Exception:
            errors = errors + 1
            print("  ERROR       ", name, frappe.get_traceback().splitlines()[-1])

if not DRY_RUN and deleted:
    frappe.db.commit()
    print("Committed.")

print("")
print("SUMMARY groups=%s kept=%s deleted=%s errors=%s" % (kept, kept, deleted, errors))
if DRY_RUN:
    print(">>> Review above, set DRY_RUN = False, tick Commit, Run again.")
print("=" * 70)
```

Customise the keep rule (newest, a specific `workflow_state`, most children) in the comment and
in the sort order; never delete without showing the keep/delete pair first.

## 6. Resumable batch update (DRY_RUN, run until `remaining` is 0)

Use when the job touches thousands of rows. Each run handles `BATCH_SIZE` rows that still match
`TODO_FILTERS`; rows already fixed no longer match, so a re-run picks up where the last one
stopped and is safe to repeat.

```python
# System Console — set FIELD = NEW_VALUE in batches; re-run until remaining = 0
# Step 1: DRY_RUN = True  -> Run, review the first batch
# Step 2: DRY_RUN = False -> tick Commit, Run again, repeat until "remaining after this run: 0"

DRY_RUN = True
BATCH_SIZE = 200
DOCTYPE = "ToDo"
FIELD = "status"
NEW_VALUE = "Closed"
TODO_FILTERS = {"description": ["like", "batch-%"], "status": ["!=", "Closed"]}

print("=" * 70)
print("Batch update |", DOCTYPE, ".", FIELD, "->", NEW_VALUE, "|", frappe.utils.get_url())
print("Mode:", "DRY-RUN" if DRY_RUN else "EXECUTE", "| batch size:", BATCH_SIZE)
print("=" * 70)

total_todo = frappe.db.count(DOCTYPE, TODO_FILTERS)
rows = frappe.get_all(DOCTYPE, filters=TODO_FILTERS, fields=["name"], order_by="name asc", limit_page_length=BATCH_SIZE)
print("matching in total:", total_todo, "| this batch:", len(rows))

done = 0
errors = 0
for row in rows:
    try:
        if DRY_RUN:
            print("WOULD  ", row.name)
        else:
            frappe.db.set_value(DOCTYPE, row.name, FIELD, NEW_VALUE, update_modified=False)
        done = done + 1
    except Exception:
        errors = errors + 1
        print("ERROR  ", row.name, frappe.get_traceback().splitlines()[-1])

if not DRY_RUN and done:
    frappe.db.commit()
    print("Committed.")

remaining = total_todo - (0 if DRY_RUN else done)
print("")
print("SUMMARY done=%s errors=%s" % (done, errors))
print("remaining after this run:", remaining)
if DRY_RUN:
    print(">>> Review above, set DRY_RUN = False, tick Commit, Run again (repeat until remaining = 0).")
print("=" * 70)
```

If a row can fail permanently (error every run), it would block progress on the next run: exclude
it with an extra filter, or fix the cause, before looping.
