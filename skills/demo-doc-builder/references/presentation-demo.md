# Presentation-style demo document (flow only)

Use this mode when the user wants "only the demonstration": a .docx a presenter pages through like slides, with no
install steps, commands or troubleshooting. It reuses the same screenshots, annotation and diagram tools, but the
document is built with `scripts/demoslides.py` (landscape, one slide per page).

## When to pick it
- "demo file", "for the presentation", "only the flow", "just like a presentation", "PW will use this to demo".
- The audience watches; the presenter talks. Keep text to a few numbered lines per slide.

## Deck shape (about 20 to 30 slides)
1. Cover (what they will see, time, "all data is fictional").
2. Agenda table (12 steps or fewer).
3. The idea: before/after table + one pipeline diagram.
4. How the pieces fit: architecture diagram + the safety-guards diagram.
5. Configuration in detail: the settings page split over 2 to 3 slides with numbered callouts, then roles and where
   secrets live. Configuration is part of the demo: show every field that changes behaviour.
6. The flow, one state per slide: open the page, choose options, the input document, the waiting screen,
   the result (whole picture), how each row was decided, fixing a row, an edge case per role, leaving and returning,
   the final action, the record it created.
7. After the flow: audit trail and who sees what, what a failure looks like, phone and tablet.
8. Control and safety table, measured results, next steps, "Questions?".

Add a short *Say:* line under diagrams. Put numbers on screenshots and use the same numbers in the text beside them.

## Screenshots for slides
- Use `"scale": 2` in the screenshot plan (and in the annotate plan). Coordinates stay in CSS pixels; the sharper image
  survives being shrunk onto a slide.
- Crop the app's left sidebar off (for Frappe at 1360 px that is the first 224 CSS px = 448 px at scale 2).
- Take a different user in each `context` when the point is "who sees what" (stock user vs manager).
- Add `"dismiss": true` to a shot when a random popup can appear (Frappe "Session Defaults" opens for some users and
  darkens the whole page). Look at every PNG before using it.
- A sticky action bar or an overflow-hidden table can clip dropdowns on the last rows. If a dropdown is cut off in the
  shot, fix the page (raise the table above the bar) rather than cropping around it.
- Split tall pages: one full settings screenshot becomes two slides by passing `crop=` to `split()`.
- Show the *seeded* example, not a live paid call: seed a replayed result so the demo is fast, free and repeatable,
  and say so on the cover.

## Layout rules (these all caused real defects)
- Landscape A4, margins 0.6 in, usable width 10.5 in, usable height about 6 in per slide.
- Give every table column an explicit width (`demoslides` does). Without it the row splits 50/50 and a wide picture
  is clipped at the column edge.
- One slide = one page. If a heading is alone at the bottom of a page, the picture is too tall: reduce `image_w`.
  Phone screenshots <= 2.4 in wide, a full-page desktop screenshot <= 5.9 in in a split, a wide band <= 9.4 in alone.
- Crop a portrait document image (an A4 invoice) to its top half; the rest is white.
- Diagrams that run wide (6 or more boxes) need `"width": 1900` or more in the diagram plan or the last box is cut.
- Remove the trailing blank paragraph risk: a table at the very bottom of a page can push an empty page. Shrink the
  picture above it.

## Demo data hygiene
- Seed with a script and keep a manifest of everything created; tear down with a script afterwards and print the
  leftover counts. Use users such as `demo.<role>@example.com` and fictional companies and tax numbers.
- If no throwaway site can be created (no database root password), use the development site, seed only fictional
  records, and say so in the hand-over.
- Delete the generator, screenshots and seed files after the user has the .docx, if they ask for only the document.

## Build and check
```bash
PY=~/.cache/demo-doc-builder/venv/bin/python
node scripts/screenshots.js plan.json            # scale 2
$PY scripts/annotate.py annotate.plan.json       # "scale": 2
node scripts/diagram.js diagrams.plan.json
$PY build_demo.py                                # uses demoslides
bash scripts/render_check.sh demo.docx           # look at every sheet
```
Count the pages: it should be about one page per slide. Fix any slide that spills onto a second page.
