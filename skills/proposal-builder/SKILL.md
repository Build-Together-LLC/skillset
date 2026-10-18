---
name: proposal-builder
description: >
  Produce a Build Together client implementation proposal as a styled .docx — the ERPNext / Frappe
  (or any custom-software) sales proposal with cover, document-control table, executive summary,
  understanding-the-business, solution stack, module scope, implementation phases, timeline,
  investment breakdown, hosting, AMC tiers, exclusions, sign-off and a requirement coverage matrix.
  Two formats are supported: LONG (detailed, ~50-65 pages, for a technical buyer who wants every
  decision recorded) and SHORT (consolidated, ~20-25 pages, for an owner who will actually read it).
  Trigger whenever the user asks to create, draft, write, shorten, lengthen or regenerate a proposal,
  quotation document, work estimate, scope-and-costing document or SOW-precursor for a client — e.g.
  "make a proposal for X", "quote this ERP work", "shorten that proposal", "add a module to the
  proposal". For non-proposal documents (SOP, RCA, spec, runbook) use document-builder instead.
---

# Proposal Builder — Build Together Client Proposals

You produce client-ready implementation proposals. Styling is inherited from the **document-builder**
house format and is not negotiable. This skill adds the *proposal-specific* structure, content
conventions, commercial patterns and page budgeting.

---

## Step 0 — Intake

Establish these before writing. Ask at most 3 blocking questions; assume the rest and record the
assumption in the document with `d.assumption(...)`.

1. **Client** — legal name, location, industry, what they actually do.
2. **Source of truth** — a meeting transcript, requirement doc, or notes. **The transcript governs.**
   If a web search or public record contradicts it, the transcript wins; public-record facts go in
   the snapshot table marked *"(public record — to confirm)"*.
3. **Format** — LONG or SHORT (see below). If unstated, default to **SHORT**; owners do not read 60
   pages. Say which you chose.
4. **Scope, phasing and price** — which modules, what starts first, rough commercials.

### Choosing the format

| | LONG | SHORT |
|---|---|---|
| Length | ~50–65 pages | ~20–25 pages |
| Sections | ~25–30 H1s + annexures | 8 H1s + 2 annexures |
| Module treatment | One H1 per module, prose + capability tables | One H3 per module, 5–7 one-line bullets |
| Use when | Technical buyer, committee review, every decision must be on record | Owner-read, negotiation copy, first send |
| Reference | `references/long-form.md` | `references/short-form.md` |

Both formats carry **the same content**. SHORT is compression, not omission — the requirement
coverage matrix (Annexure A) is what guarantees nothing was dropped, so it stays at full length in
both.

---

## Setup — the toolchain

```python
import sys
sys.path.insert(0, str(SKILL_DIR.parent / "document-builder" / "scripts"))  # SKILL_DIR = this skill's directory
from docbuilder import DocBuilder
d = DocBuilder()          # NOTE: no args — build the cover manually, see below
```

Run the generator with a Python that has `python-docx` — the project venv if there is one:

```
python <generator>.py
```

Write the generator to the session scratchpad, run it, verify, then report the absolute output path.
Keep the generator — regenerating from an edited script is how revisions are made. Never hand-edit
the .docx.

**Output path:** `docs/proposals/Proposal - <Client> (<Stack>).docx`, relative to the project —
or wherever the user asks. Never hardcode an absolute path.
e.g. `Proposal - AMK Bearings ERP (ERPNext + Frappe CRM, Projects & HR).docx`

---

## The cover — do NOT use `d.cover()`

The house proposal cover is four centred paragraphs then the Document Control table:

```python
d.body("IMPLEMENTATION PROPOSAL", bold=True, align="center", size=20, color="1A3C5E")
d.body("<one-line solution descriptor>", italic=True, align="center", size=13, color="333333")
d.body("<Client>  •  <Bucket A>  •  <Bucket B>", align="center", size=12, color="2E75B6")
d.body("<4-6 line paragraph: what this delivers and the one commercial hook "
       "(zero licence fees; you own the source code)>")
d.spacer()
d.table(["Field", "Detail"], [...], caption="Document Control", widths=[1.4, 5.1])
```

Document Control rows: Document Title, Reference (`BTG/PROP/<CLIENT-SLUG>/<YYYYMMDD>`), Prepared For,
Prepared By (Build Together), Version / Date + validity (30 days), Basis, Investment one-liner,
Contents one-liner (SHORT) , Confidentiality.

### Caption numbering gotcha

`d.h1()` increments the section counter and resets the table counter, so captions read
`Table <section>.<n>`. The cover table lands before any H1 and prints as `Table 1.1`.

- **SHORT** — first H1 is `1. Executive Summary`, so numbering aligns naturally. Do nothing.
- **LONG** — if you add a `Table of Contents` H1, it consumes section 1 and throws every later
  caption out by one. Immediately after it, reset:
  ```python
  d.h1("Table of Contents")
  d._section_no = 0        # contents page is not a numbered section
  ```

---

## Section banners

Every H1 is preceded by a banner, which renders at the foot of the previous page:

```python
d.banner("4. SCOPE — MODULE BY MODULE", "Everything in scope, stated in brief")
d.h1("4. Scope — Module by Module")
```

Banner title = the section number and name in caps; subtitle = a short editorial line, not a repeat.

---

## Mandatory content rules

- **The transcript is the decision record.** Where the client made an explicit call ("we are not
  leaving Tally", "no auto-reordering", "in-transit only on vendor dispatch"), state it as a
  deliberate design decision and say *why*, using `d.banner("Deliberate decision", "...")`. Clients
  buy from a vendor who listened.
- **Quote their requirement back.** In LONG, open each module sub-section with *"Your Requirement: …"*.
  In SHORT, the coverage matrix does this job.
- **Never invent capability.** If something needs custom build, say "(custom build)". If it depends
  on a third party (an API, an SDK, a device), say so and put it in exclusions.
- **Annexure A — Requirement Coverage Matrix is mandatory in both formats.** One row per requirement
  from the source, columns `Your Requirement | How It Is Delivered | Type`, where Type is
  `Std` / `Config` / `Custom` (or combinations). This is the artefact that proves nothing was missed;
  it is the last thing to cut, never the first.
- **Flag what is unresolved.** Close with Open Questions for Discovery — say plainly that none of them
  block the proposal.
- **No blank table cells.** Use `N/A` or `—`.
- **Assumptions are visible**, via `d.assumption(...)`, never buried in prose.

Reusable boilerplate — hosting plans, AMC tiers, payment terms, exclusions, sign-off table, app stack,
"why ERPNext wins" — is in `references/house-content.md`. Copy from there; keep the numbers current.

---

## Commercials

Structure the investment section as:

1. **One-time implementation, by module** — `# | Module | Scope | Effort | Cost (INR)` with a total row.
   Module costs should reconcile to the effort figures.
2. **Phasing option** — track-wise or phase-wise split so the client can commission in stages, with a
   note that parallel commissioning is what makes the headline timeline possible.
3. **Hosting** — Frappe Cloud plan table, paid by the client directly, explicitly *not* bundled.
4. **Optional future modules** — everything deliberately out of this phase, priced. This is where
   deferred scope goes so it reads as planned, not forgotten.
5. **Recurring costs** — hosting, domain, usage-based third parties, AMC.
6. **Payment terms** — milestone-linked bullets summing to 100%.

All prices exclusive of GST, stated as indicative and confirmed after discovery.

### Person-weeks

One person-week = one person full-time for one week. It is **effort**, not calendar time; parallel
staffing is what compresses it. Publishing effort justifies the price *and* exposes the implied rate
(total ÷ person-weeks). **Ask the user before putting an effort column in the pricing table** — some
clients will anchor on the rate. Keeping effort in a separate section-6 table, away from the money, is
the safer default.

---

## Page budgeting

H1s force a page break, so a proposal cannot be shorter than its H1 count. Cost per element, roughly:

| Element | Relative cost | Note |
|---|---|---|
| Bullet, one line | 1× | cheapest way to state a capability |
| Table row, one line | ~1.4× | 0.25 line of chrome per row on top of content |
| Table row wrapping to 2 lines | ~2.2× | watch cell width vs text length |
| H1 | up to a full page | page break plus part-page waste |

Practical levers, in the order to reach for them:

1. **Turn module capability tables into bullet lists** — same content, roughly half the space.
2. **Merge H1s** — every section removed saves the break plus its whitespace.
3. **Trim table cells to fit one line** — a cell at 5.0" fits ~65 characters per line.
4. **Delete genuine duplication** — a per-module summary table that restates the module body, or a
   deliverables table that restates both.
5. Only then consider cutting content, and say what you cut.

### Estimating length

LibreOffice often **fails silently headless** — it exits 0 and writes no PDF, so you cannot rely on
converting to count pages. Use the estimator instead:

```
python "$SKILL_DIR/scripts/estimate_pages.py" <file>.docx
```

Add `--breakdown` to see which sections are consuming the pages — always do this before cutting, so
you cut where the pages actually are rather than where you assume they are.

The model simulates the H1 page breaks and lands close to 1:1 against a rendered document (a proposal
it scored 63 rendered as 62 pages). Treat it as ±10%. **Tell the user it is an estimate and ask them
to confirm the real count when they open it** — do not state a page count as fact.

---

## Self-verification — before reporting done

```python
from docx import Document
from docx.table import Table
doc = Document(path)
assert doc.styles['Normal'].font.name == 'Times New Roman'
assert [p for p in doc.paragraphs if p.style.name == 'Heading 1']
for p in doc.paragraphs:
    for r in p.runs:
        assert r.font.name in ('Times New Roman', 'Courier New', None), r.font.name
for b in doc.element.body.iterchildren():          # no blank cells
    if b.tag.endswith('}tbl'):
        for row in Table(b, doc).rows:
            assert all(c.text.strip() for c in row.cells)
```

Checklist:

- [ ] Cover block, then Document Control table, before any prose
- [ ] Executive Summary opens the body and stands alone
- [ ] Every H1 has a banner; captions run `Table <section>.<n>` in step with the section numbers
- [ ] Every requirement in the source appears in Annexure A
- [ ] Investment section reconciles: module costs sum to the total; effort sums to the stated figure
- [ ] Hosting, AMC, exclusions, payment terms, sign-off and open questions all present
- [ ] Times New Roman throughout; no blank cells
- [ ] Page estimate run and reported as an estimate

## Tone

Confident, concrete, no marketing adjectives. Write for an owner deciding whether to spend money.
State decisions and their reasons. Where you disagree with the client's instruction, implement it and
note the trade-off once — never argue in the document.
