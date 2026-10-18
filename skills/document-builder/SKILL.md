---
name: document-builder
description: >
  Produce any formal document as a styled .docx (or Markdown) using the house
  format: Times New Roman 12pt justified, real Word heading styles that Google Docs picks up on
  upload, and the mandatory skeleton of overview table → consolidated summary → detailed flow.
  Trigger this skill whenever the user asks to create, write, prepare, draft or format ANY
  document — an SOP, runbook, RCA / post-mortem, requirements or spec doc, release / deployment
  notes, audit report, training or handover doc, process note, proposal, meeting minutes, policy,
  status report, or "make a doc / docx / Google Doc for this". Also trigger on follow-ups like
  "make it a proper document", "put this in a docx", "format this for Google Docs", "add a section
  to that doc", or "regenerate the document". This is the general-purpose successor to
  feature-to-prd — use feature-to-prd only when the ask is specifically a Frappe feature PRD.
---

# Document Builder — House Format

You produce polished, upload-ready documents. The styling is **not negotiable**: every document
published from this skill looks the same, so the reader's attention goes to the content.

Do **not** hand-roll `python-docx` boilerplate. A tested library lives at
`scripts/docbuilder.py` next to this file — import it and use its helpers. It already encodes
every rule below.

---

## Step 0 — Intake

1. Identify the **document type** (SOP, RCA, spec, release notes, …) and the **audience**
   (engineers, HR ops, management, external).
2. Identify the **subject** — the system, feature, incident or process being documented.
3. Flag **at most 3 blocking ambiguities**. Do not stall: make a reasonable assumption, and record
   it in the document with `d.assumption("...")` rather than leaving a gap.

## Step 0.5 — Output format

Ask once, unless the user already said:

> "Word (.docx), Markdown (.md), or PDF?"

- **.docx / .pdf** → use `docbuilder.py`. For PDF, generate the .docx and tell the user to export
  (or convert with `libreoffice --headless --convert-to pdf <file>.docx` if available).
- **.md** → plain Markdown with `#`/`##`/`###` headings and pipe tables. Same *structure* as below,
  no styling code.

---

## MANDATORY document skeleton

Every document follows this order. Do not reorder or drop parts.

| Position | Part | Rule |
|---|---|---|
| Cover | Title block | Title + subtitle + a metadata table (prepared by, date, status, version) |
| **Pages 1–2** | **Overview table(s)** | **The document ALWAYS opens with a table**, before any prose |
| Next | **Consolidated Summary** | The whole document compressed — readable standalone |
| Then | **Detailed Flow** | The actual body, step by step |
| End | Open Questions / Sign-off | Anything needing a decision before action |

### 1. Overview table (pages 1–2) — always first

The reader must grasp the entire document from the first two pages **without reading prose**.
Use one or two tables, e.g. a document-control sheet plus an at-a-glance scope/findings table.
Pick columns that suit the doc type:

- SOP / runbook → `Step | Action | Owner | System | Expected Result`
- RCA / incident → `Item | Detail` (impact, root cause, fix, status) + a timeline table
- Spec / PRD → `Component | Type | Purpose | Owner`
- Release notes → `App | Change | PR | Risk`
- Audit → `Area | Finding | Severity | Action`

Keep it to 1–2 pages. If it overflows, move detail into the flow section — the header row repeats
automatically across pages.

### 2. Consolidated Summary

Prose (justified), 3–8 short paragraphs or bullets. State conclusions and decisions, not
narration. Someone who reads *only* this section must be able to act correctly.

### 3. Detailed Flow

The step-by-step body. Use `h2` per major step and `h3` for sub-steps. Each step should say
**what happens, who does it, what system it touches, and what the expected result is.** Use
`d.code(...)` for commands, SQL, pseudocode or mermaid diagrams, and `d.banner(...)` for warnings.

### 4. Open Questions

Close every document with what still needs sign-off. If nothing is open, say so explicitly.

---

## Formatting rules (encoded in `docbuilder.py`)

### Typography
- **Times New Roman everywhere** — headings, body, tables. The only exception is `d.code()`,
  which uses Courier New for legibility.
- Body **12pt**, **justified**, black, line spacing **1.15**.
- Page: US Letter, 0.75" margins.

### Headings — the Google Docs requirement
Headings **MUST** use the built-in Word `Title` / `Heading 1` / `Heading 2` / `Heading 3` styles.
`docbuilder` does this via `add_heading()`. **Never fake a heading** with a bold paragraph — Google
Docs builds its outline, navigation pane and table of contents from these styles, and a bold
paragraph is invisible to it.

| Level | Size | Colour | Behaviour |
|---|---|---|---|
| Title | 24pt bold | `1A3C5E` | Centred cover title |
| Heading 1 | 15pt bold | `1A3C5E` | New page before (except the first) |
| Heading 2 | 14pt bold | `2E75B6` | — |
| Heading 3 | 13pt bold | `4A86C8` | — |

### Tables
- Left aligned, header row shaded `BDD7EE` bold 11pt, body 11pt `333333`, borders `AAAAAA`,
  alternating rows `F2F7FB`, header repeats across page breaks.
- **Every table gets a caption above it**: `Table <section>.<n>: Description`, auto-numbered by
  `d.table(..., caption="...")`. The counter resets at each `h1`.
- **Never leave a cell blank** — write `N/A`.

### Palette
`1A3C5E` navy (H1/banner) · `2E75B6` blue (H2) · `4A86C8` light blue (H3) · `BDD7EE` table header
· `F2F7FB` alt row · `333333` body grey · `AAAAAA` border

---

## Using the library

```python
import sys, pathlib

# Point this at the scripts/ directory next to this skill's SKILL.md, wherever it is installed.
SKILL_DIR = pathlib.Path("~/.claude/skills/document-builder").expanduser()
sys.path.insert(0, str(SKILL_DIR / "scripts"))
from docbuilder import DocBuilder

d = DocBuilder(
    title="Salary Slip Visibility — Operations Runbook",
    subtitle="ERPNext / HRMS · Employee Self Service",
    meta={"Prepared by": "Aman", "Date": "2026-07-24", "Status": "v1.0", "Audience": "HR Ops"},
)

# --- pages 1-2: the table, always first ---
d.h1("Document Overview")
d.table(["Item", "Detail"], [
    ["Scope", "Employee access to own salary slips"],
    ["Systems", "ERPNext, HRMS"],
    ["Owner", "HR Operations"],
], caption="Document control sheet", widths=[2.0, 4.5])

# --- then the summary ---
d.h1("Consolidated Summary")
d.body("Salary Slip carries no if_owner permission, so visibility depends entirely on ...")
d.bullet("Exactly one User Permission must exist per employee.")
d.assumption("All slips for the period are submitted, not draft.")

# --- then the flow ---
d.h1("Detailed Flow")
d.h2("Step 1 — Verify the employee linkage")
d.body("Confirm Employee.user_id matches the login being tested.")
d.code("SELECT name, user_id FROM tabEmployee WHERE name='HR-EMP-00235';")
d.banner("Warning", "Never leave user permissions deleted — it exposes all slips")
d.table(["Check", "Expected"], [["Role", "Employee"], ["Slips", "docstatus = 1"]],
        caption="Verification matrix")

d.h1("Open Questions")
d.bullet("Should ex-employees retain slip access after exit? — pending HR sign-off")

d.save("docs/Salary_Slip_Runbook_20260724.docx")
```

### API reference

| Call | Purpose |
|---|---|
| `DocBuilder(title, subtitle, meta, toc=False)` | Cover block + optional TOC field |
| `d.h1/h2/h3(text)` | Real Word headings; `h1` page-breaks and resets table numbering |
| `d.body(text, bold, italic, align)` | Justified 12pt paragraph |
| `d.bullet(text, level)` / `d.numbered(text)` | Lists |
| `d.table(headers, rows, caption, widths, alt_rows)` | Styled auto-captioned table |
| `d.caption(desc)` | Standalone caption (rarely needed) |
| `d.code(text)` | Monospace shaded block — SQL, mermaid, pseudocode |
| `d.banner(title, subtitle)` | Navy warning/divider banner |
| `d.assumption(text)` | Italic `ASSUMPTION:` note |
| `d.spacer()` / `d.page_break()` | Spacing |
| `d.save(path)` | Write the file, returns the path |

---

## Hyperlinks

`Link(text, url)` renders as real Word hyperlink field, not blue text. It works anywhere a string
does — body text, bullets, table cells, and `meta` values — and a list mixes links with plain runs.

```python
from docbuilder import DocBuilder, Link, pr_url, commit_url, issue_url, jira_url

REPO = "my-org/my-repo"

d.table(["Ref", "Change", "Jira"],
        [[Link("#234", pr_url(REPO, 234)),
          "Warehouse batch pricing removed",
          Link("ABC-270", jira_url("ABC-270"))],
         [Link("abc1234", commit_url(REPO, "abc1234")), "Direct commit", "—"]])

d.body([Link("github.com/" + REPO, "https://github.com/" + REPO), "  —  prod → develop"])
```

The four URL helpers are conveniences, nothing more — `pr_url`, `commit_url`, `issue_url` take an
`owner/repo` string. `jira_url(key)` reads `JIRA_BASE_URL` from the environment, or takes `base=`;
it raises rather than default to anyone's Jira site, because a wrong base produces links that look
right and go nowhere. Pass any URL to `Link` directly when the helpers do not fit.

Verify after saving — a document that should have links and has none means `Link` was stringified
somewhere:

```python
import docx
from docx.oxml.ns import qn
doc = docx.Document(PATH)
print("hyperlinks:", len(doc.element.body.findall('.//' + qn('w:hyperlink'))))
```

## Output rules

- Filename: `<Doc_Type>_<Subject>_<YYYYMMDD>.docx`, underscores not spaces.
- Save to the path the user asks for; default to `docs/` under the current project. Never
  hardcode an absolute path — the skill has to run on any machine.
- Write the generator to the session scratchpad, run it, then **verify** (see below) and tell the
  user the absolute output path.
- Never invent facts. If the document states system behaviour, confirm it from the codebase or
  say it is unverified.

## Tone

Terse and actionable. Correct Frappe/ERPNext terminology. No marketing language. Write for
someone who has to *do* something with the document.

---

## Self-verification — run before reporting done

After saving, re-open the file and check programmatically:

```python
from docx import Document
doc = Document(path)
assert doc.styles['Normal'].font.name == 'Times New Roman'
# headings must be real styles, not bold paragraphs
heads = [p.style.name for p in doc.paragraphs if p.style.name.startswith(('Heading','Title'))]
assert heads, "no real heading styles — Google Docs will not build an outline"
# no stray fonts
for p in doc.paragraphs:
    for r in p.runs:
        assert r.font.name in ('Times New Roman', 'Courier New', None), r.font.name
```

Checklist:
- [ ] Document opens with a **table** on pages 1–2, before any prose
- [ ] **Consolidated Summary** follows, then the **detailed flow**
- [ ] Headings use built-in `Heading 1/2/3` styles (verified above)
- [ ] Times New Roman throughout; body 12pt justified, 1.15 spacing
- [ ] Every table has an auto-numbered caption; no blank cells
- [ ] Each `h1` starts a new page (except the first)
- [ ] Document ends with Open Questions / sign-off
