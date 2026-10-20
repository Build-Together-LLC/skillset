# Updating an existing guide or demo (the product changed)

Use this when the user says "update the demo", "make a new one as per the updated things", "delete the old and create new".
Most of the work is already done: the old build folder has the generator, the plans, the seed and the pictures.

## 1. Find and keep the old build
- Look for the folder beside the old .docx (for example `docs/<topic>-build/`): `build_guide.py`, `build_demo.py`, `plan_*.json`,
  `seed/`, `work/final/`. Keep all of it until the new documents are built. Delete the old .docx files last, and only when asked.
- If there is no build folder, treat it as a new document (Step 0 of SKILL.md) and read the old .docx for the structure.

## 2. Work out what changed
- `git log --since=<date of the old document> --stat` in the product repo, and read the messages. Make a table of
  change -> sections and pictures it touches. Put a short "What changed since <old version>" table in the new overview.
- Check the facts again, not only the diff: field names, button wording, URLs, roles, defaults. Run the new code paths and
  keep their real outputs (message text, error text, emails).

## 3. Decide each picture
| Case | Do |
|---|---|
| Screen unchanged | Reuse the old file. Do not retake it |
| Screen changed (new field, moved button) | Retake it into a NEW folder (`final2/`), never over the old one |
| New feature | New shot, new diagram, new table |
| Old picture now wrong (old URL, old wording in a screenshot of an in-app help page) | Fix the product text or retake. Do not leave a picture that disagrees with the text |

New and old pictures live in different folders so a stale file can never be picked up by accident.

## 4. Reuse the build script, do not retype it
Copy the old generator, keep its header (helpers, theme, cover), and pull unchanged blocks from the old script by line number:

```python
OLD = open("build_guide.py").read().split("\n")

def old(first, last, rep=()):
    """Run lines first..last-1 of the old generator. rep = [("7.3  The emails", "7.4  The emails")] renumbers headings."""
    text = "\n".join(OLD[first - 1 : last - 1])
    for a, b in rep:
        text = text.replace(a, b)
    exec(compile(text, "old", "exec"), globals())
```
Find the line numbers with `grep -n "d.h1(\|d.h2(" build_guide.py`. Rewrite the sections that changed, insert the new ones, update the
cover (version, date, "code checked"), the contents table and every "Section n.m" cross reference. Split a large body into
`part1.py ... partN.py` files and concatenate them, so each part stays reviewable.

## 5. Re-seed
- Seeds that hard-code dates go stale: compute them from today. Re-run the seed, then add only what the new features need
  (a holiday, a leave day, a manager, a record with no booking yet).
- Save every single doctype you change for the demo to `originals.json` first (`templates/frappe_seed_teardown.py` does this).
- Do not run the product's test suite on that site until the shots are done: tests often reset settings pages.

## 6. Build, review, hand over
- Render (`render_check.sh`), read every sheet, fix, rebuild. Then `privacy_scan.py` and `contact_sheet.py` (see `review-checklist.md`).
- Name the new files with the new date in the same folder; delete the old files only after the new ones open cleanly, and say which you deleted.
- Tear the demo data down, restore the settings from `originals.json`, stop servers you started, delete scratch files.
- Say what you did NOT verify (real devices, live services) and any product bug you found and fixed on the way.
