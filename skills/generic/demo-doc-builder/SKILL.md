---
name: demo-doc-builder
description: >
  Build a complete, polished step-by-step demo / setup / how-to guide as a .docx from a short
  brief: real annotated screenshots taken from a throwaway demo environment, clean diagrams and
  file-tree pictures, example keys, local + Docker + VPS + managed-hosting (for example Frappe
  Cloud) instructions with exact commands and "what you should see" results, key rotation, testing
  checklists, troubleshooting and security sections. Times New Roman 12 pt, selectable colour
  theme, every URL a clickable hyperlink, numbered figures and tables. Trigger on: "make a demo
  doc", "setup guide with screenshots", "how-to document with images", "installation guide for
  <product/app>", "document this setup step by step", "user manual with screenshots", "write the
  docs for this feature and include screenshots", "docx with diagrams and commands", or any request
  to turn a small description into a ready-to-share guide with pictures. Also builds a presentation-style
  "flow demo" .docx (one landscape slide per page, big numbered screenshots, speaker lines) when the user
  wants only the demonstration for a talk: trigger on "demo file", "for the presentation", "only the flow",
  "present it like slides". For plain formal documents without screenshots (SOP, RCA, spec, minutes) use
  document-builder instead.
---

# Demo Doc Builder

You turn a **small brief** into a **finished guide**: the reader should be able to follow it from a clean
machine to a working result, and every picture, command and link in it must have been produced or
verified by you. Do not hand back a draft with gaps.

Everything lives next to this file:

| Path | What it is |
|---|---|
| `scripts/setup.sh` | one-time environment (Python venv with python-docx + Pillow, playwright-core, browser check) |
| `scripts/demodoc.py` | the document library (themes, hyperlinks, callouts, code blocks, tables, figures) |
| `scripts/build_from_spec.py` | JSON spec -> .docx |
| `scripts/screenshots.js` | JSON plan -> PNG screenshots (headless Chrome, multi-user contexts, `scale` for sharp 2x images, `dismiss` to close stray popups, `targets` records field boxes, `element`/`clip` for partial shots) |
| `scripts/annotate.py` | numbered badges, boxes, arrows, **pixelate/blur secrets** (`scale` matches 2x screenshots), `{"box": [shot, n]}` draws on a recorded target |
| `scripts/crop.py` | crop screenshots by CSS pixels (sidebar off, tall pages cut) |
| `scripts/contact_sheet.py` | many images on one labelled sheet, to review a batch in one look |
| `scripts/privacy_scan.py` | scan the finished .docx for foreign e-mails, tokens, keys and a deny list of real names |
| `scripts/chat_mock.py` | phone / chat screens from a transcript JSON built from the product's real strings |
| `scripts/demoslides.py` | **presentation mode**: landscape one-slide-per-page .docx (`slide`, `split`, `pair`, `alone`, `quad`, `say`) |
| `scripts/diagram.js` | JSON -> flow diagrams and file-tree pictures |
| `scripts/render_check.sh` | docx -> PDF -> contact sheets so you can look at every page |
| `templates/brief.md`, `templates/themes.json` | what the user fills in, the colour themes |
| `templates/frappe_seed_teardown.py` | manifest-based seed and teardown of fictional records, restores the settings it changed |
| `templates/frappe_run.py` | run a seed or teardown script inside a site without `bench console` (the console mangles multi-line scripts) |
| `references/*.md` | hosting recipes, Frappe demo-data lessons, security rules, writing style, **presentation-demo**, **updating-a-document**, **review-checklist**, **chat-mockups** |
| `examples/` | a complete working sample: `bash examples/run-example.sh purple`; `slides_example.py` shows presentation mode |

Read `references/security-and-privacy.md` and `references/writing-style.md` before you start. Read
`references/hosting-recipes.md` when the guide covers servers, Docker or managed hosting,
`references/frappe-demo-data.md` when the product is a Frappe / ERPNext app,
`references/updating-a-document.md` when an older guide or deck of the same product exists,
`references/chat-mockups.md` when the flow runs in a chat, and `references/review-checklist.md` before every hand-over.
In the commands below `$SKILL` is this skill's folder (the one that holds this file).

---

## Three kinds of output (pick in Step 0)

| The user says | Build | Read |
|---|---|---|
| "setup guide", "how-to", "document the setup", "user manual" | the full guide (Steps 1 to 6 below) | `references/*.md` |
| "demo file", "for the presentation", "only the flow", "only the demonstration", "like slides" | the **presentation demo**: configuration + flow only, landscape, one slide per page | `references/presentation-demo.md` |
| "update", "new one as per the updated things", "delete the old and create new", or an old document and its build folder exist | an **update**: reuse the old generator, seed and pictures; retake only what changed | `references/updating-a-document.md` |

For the presentation demo keep Steps 1 to 3 and 5 to 6, replace Step 4 with `scripts/demoslides.py`, take screenshots at
`"scale": 2`, show configuration in detail, and leave out install, hosting, key rotation, troubleshooting and
command cheat-sheets. If the user wants both, build the guide first and the slides second from the same screenshots. If an older version exists, update it
(third row) instead of starting again: it keeps the structure the reader already knows and is much faster.

## Step 0. Intake (do not stall)

Use `templates/brief.md`. If the user gave a brief, extract the fields; ask **at most three** questions,
only for what you truly cannot infer. Defaults: theme `green`, A4, demo data, save to `./docs/<topic>/`,
cover the local **and** the server path.

Offer the themes by name: `green` `navy` (deep navy/blue) `blue` `purple` `orange` `teal` `slate`.

## Step 1. Environment

```bash
bash $SKILL/scripts/setup.sh
```
It prints the python, playwright, browser and LibreOffice paths. Use that venv's python for the scripts:
`PY=~/.cache/demo-doc-builder/venv/bin/python`. If Chrome is missing, tell the user; do not skip screenshots.

## Step 2. Gather facts (never write from memory)

- Fetch the vendor's own docs for install, security, API and webhooks (WebFetch / WebSearch). Quote their
  recommended settings. Note the version you tested.
- Read the repo/branch the guide documents (settings fields, endpoints, roles) so field names and
  behaviour in the guide are exact.
- Verify **every URL you will use**: `curl -s -o /dev/null -L -w '%{http_code} %{url_effective}\n' <url>`.
  Fix or drop anything that is not 200. Sites that block curl (403) may be listed, say "not machine-verified".
- Run the real commands you will document (or their safe equivalents) and keep the real outputs for the
  "What you should see" lines. If you cannot run something, say so in the guide.

## Step 3. Demo environment and screenshots

1. Build a throwaway environment with demo data (see `references/frappe-demo-data.md`). **Never** shoot a
   real site, real customers, or personal numbers.
2. Write a screenshot plan (`scripts/screenshots.js` header documents it). One shot per state a reader will
   see: empty state, form filled, success message, error message, each step of the main flow, each role's view.
   Use `contexts` for a second user.
3. Take them: `node scripts/screenshots.js plan.json`. Read the printed console/network problems; a 404 in a
   shot means the shot is wrong or the product is broken, fix it first.
4. **Look at each PNG** (Read tool, or a batch on one sheet with `contact_sheet.py`) and choose annotation coordinates from what you see.
   Better: give a shot `targets` (`[{"n": 1, "sel": "[data-fieldname=email]"}]`); the plan run records their boxes and annotate uses them.
5. Annotate: `python $SKILL/scripts/annotate.py annotate.json` (badges 1..n that match a table/list in the text,
   boxes around the thing to use, arrows, or `{"box": ["shot", 1]}` for a recorded target). **Pixelate** QR codes, keys, tokens, e-mails,
   phone numbers and any list that shows real people. Crop with `crop.py` (sidebar off).
6. Diagrams: `node scripts/diagram.js diagrams.json`. Always include an architecture flow, one per
   deployment (local / server / managed host), a "where the files live" tree for server installs, and a
   flow for any procedure with an order (key rotation).
7. Tear the demo environment down afterwards and make sure nothing real was changed.

## Step 4. Write the document

Standard structure (drop only what truly does not apply):

1. Cover (title, subtitle, version / tested-with table with links, WARNING that all values are examples)
2. What is inside + where everything lives (repo, branch, folders, files as links)
3. Overview with the architecture diagram, and a glossary of the words used
4. Prerequisites (checklist table with a "how to check" command)
5. Get the app / install it
6. Generate the keys and secrets: commands + **made-up example values** in a table
7. Run it **locally** (Docker) and on a **server/VPS**, and on any **managed host** the user named
   (see `references/hosting-recipes.md`): exact commands, file locations tree, firewall, HTTPS, backups, updates
8. Configure (field table matching the numbered screenshot, test button/command, failure messages)
9. First use (numbered steps, one screenshot per state, statuses table)
10. Daily use, then **several users / roles / instances** with access rules and screenshots of each view
11. **Regenerating keys**: every secret, the order, what breaks in between, how to verify, leaked-key checklist
12. **Testing**: connection checklist, manual scenario checklist, automated tests with commands and expected output
13. **Troubleshooting** (symptom, likely cause, fix with the proving command)
14. **Security summary**: what the app enforces, what the reader must do, link to the vendor security page
15. Command cheat-sheet and a links table

Typography is fixed by the library: **Times New Roman 12 pt**, justified body, real Word headings, tables 11 pt,
code blocks in Courier New on a dark panel. Colours come from the theme. Do not override fonts.

Hyperlinks: **every** URL (body, tables, code blocks, bullets) is turned into a link automatically. Use
`[[label|url]]` for named links. Mention a repo file or page? link it.

Two ways to write the content:

```python
# A. Python (flexible)
import sys; sys.path.insert(0, ".../demo-doc-builder/scripts")
import demodoc as d
d.init(theme="purple", footer="Acme setup guide", author="Name", title="Acme setup guide")
d.cover("Acme", "Setup guide", rows=[["Version", "1.0"]], note="All values are examples.")
d.h1("1  Overview"); d.p("Docs: https://docs.acme.example"); d.img("a.png", "Settings page", label="settings")
d.p("See Figure {fig:settings}."); d.table([["#", "Field"], ["1", "Host"]], caption="Fields")
d.code("# check\ncurl -i https://acme.example/ping", "Terminal"); d.callout("SECURITY", "Rotate keys yearly.")
d.save("guide.docx")
# B. JSON spec -> python scripts/build_from_spec.py spec.json out.docx --theme teal   (see examples/spec.json)
```

Helpers: `h1 h2 h3 p bullets steps code callout(NOTE|TIP|WARNING|EXAMPLE|SECURITY) table img expect cover
contents pagebreak spacer link figrow fit`. Figures and tables are numbered automatically; refer to them with
`{fig:label}` / `{tbl:label}` so numbers never drift when you insert content.

## Step 5. Check it like a reader

```bash
bash $SKILL/scripts/render_check.sh out.docx      # prints contact-sheet paths
```
Read **every sheet**. Fix: cropped images, code blocks split across pages, orphan headings, overflowing tables,
wrong numbering, a missing hyperlink. Re-run until clean. Then run `privacy_scan.py doc.docx --deny names.txt`
(real names and numbers you saw while shooting) and go through `references/review-checklist.md`. Pictures need your eyes: contact sheets.

## Step 6. Hand over

Tell the user: the file path, page count, what you verified (links, commands, screenshots) and what you could not
(say so plainly), any correction to something you said earlier, and what they must do themselves (for example
install Docker). Keep it short. Keep the generator script (`build_guide.py`) and the image folder beside the .docx
so the guide can be regenerated after a change.

## Rules that never bend

- Demo data only. Pixelate secrets. All example values are labelled examples.
- No claim without a source or a run. Say "not verified" where that is true.
- Every URL clickable, every URL checked.
- Times New Roman 12 pt body. Theme colours only. Real heading styles.
- Do not commit or publish the document unless asked.
- Never stop a server or process with `pkill -f` / `pgrep -f | xargs kill` (it kills your own shell). Use the pid from `lsof -ti :<port>`.
- Leave nothing behind: demo data torn down, changed settings restored, servers and temporary API keys you started or created removed.
- Look at every screenshot before using it: stray popups (Frappe Session Defaults), clipped dropdowns and secrets are common.
- If the user later asks to delete related files, keep only the one document they name.

## Related skills

- A narrated screen-recorded video of the same flow (real recording, scene cards, soft voice-over, privacy scan): `flow-video-builder`.
  Build the guide first; its storyboard and transcript are a good start for the video.
- Short GIFs and tutorial clips for a help page: `responsive-ui-walkthrough-media`.
- Formal documents without screenshots: `document-builder`.
