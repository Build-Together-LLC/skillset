---
name: "vipl-invoice-layouts"
description: "Read a VIPL supplier invoice PDF without an AI call by using that supplier's saved layout (regexes for the header and item rows), and write a new layout when a supplier has none. Use when someone asks to read, parse, extract or scan a supplier invoice for VIDIRA / VIPL, to add or fix a supplier's layout in Supplier Invoice Profile, when an invoice 'returns no data' or the skill 'stops to ask', or to cut the API cost of the Scan Invoice page. Covers Varroc, Shree Amba (Aerostar), Rockman, Texspin, SAP Swiss, FCC and Remsons today; camera scans and any other supplier fall back to the AI read."
---

# VIPL — read supplier invoices from a saved layout

The Scan Invoice page in `vidira_group` (ERPNext V16) turns a supplier invoice into a draft Purchase
Receipt. A **layout** lets a known supplier's PDF be read on the server with no AI call. The AI
read stays as the fallback and as the way new layouts are learned.

## The decision, in order

1. Take the PDF text with pypdf in `layout` mode (`page.extract_text(extraction_mode="layout")`).
   A photo, a scan or any file with no text goes straight to the AI. Do not try to read it locally.
2. Find a **Supplier Invoice Profile** with a Layout whose every `detect` regex appears in the text.
   None found: AI read.
3. Parse the header and rows with that layout, then check the result (below). Any check fails: AI read.
4. Otherwise use the local result. Provider shows **Local layout**, tokens and cost are 0.

Never stop to ask the user about MRP, item code or unit. Return the result with the missing
values empty and a short note. A reply that asks a question is read by a pipeline as "no data" —
that is exactly how the old `SKILL.md` failed on Spark Minda, which had no supplier path.

## Where things live

| What | Where |
|---|---|
| Layout (live) | `Supplier Invoice Profile` → **Local Reader** → **Layout** (JSON), one profile per Supplier |
| Item code rules | Same profile, **Item Code Rules** table (pattern + replacement, e.g. `AM-(\d+)` → `L\1`) |
| Reader | `vidira_group/inward_scan/layouts.py` |
| Learning | `vidira_group/inward_scan/learn.py` |
| Samples and rules | `references/layouts/` (seven layouts + `index.json` with each supplier's item code rules); in the app, `inward_scan/sample_layouts/` and `samples.install()` |
| Settings | `Inward Scan Settings`: **Always Read With The AI Provider** (off), **Learn Layouts From AI Reads** (off) |

Layout format and every field: `references/layout-format.md`. Which supplier is ready and why:
`references/supplier-status.md`.

## Checks that must pass before a local read is used

- At least one item row, and every row has a code and a quantity above zero.
- The sum of row `taxable` equals the printed subtotal (within ₹1 or 0.1%), when a subtotal is printed.
- The sum of row `qty` equals the printed total quantity, when one is printed.

A layout that reads rows but fails a check is rejected silently and the AI reads the file. This is
what stops a changed supplier layout from booking wrong numbers.

## Which PDFs can be read locally

Check the PDF **Producer** first (`pdfinfo file.pdf`). Software-generated invoices (SAP forms,
TallyPrime, wkhtmltopdf, Reporting Services) have clean text. **Adobe Scan, CamScanner and similar
are camera scans**: their text layer is OCR with errors (`g90.00155..O0`, HSN fused with quantity,
dropped digits), so a layout would fail its checks and fall back anyway. Do not write layouts for them.
Of the 53 sample PDFs only about ten are software-generated; the rest are scans.

## Write a layout for a new supplier

Do this only with a PDF that has a text layer and, ideally, a booked Purchase Receipt for it.

1. Print the layout text of the whole PDF and look at it. Do not write regexes from memory.
2. `detect`: two or more markers that appear on every invoice of this supplier and on no other
   (its name in the footer, a column title). Not the buyer's name, which is always Vidira.
3. `header`: one regex per field, exactly one capture group each. Fields: `supplier_name`,
   `supplier_gstin`, `document_no`, `document_date`, `subtotal`, `tax_total`, `grand_total`,
   `total_qty`. Leave out any field the invoice does not print. `date_format` is a strptime string.
4. `row`: one regex run with `re.M` over the whole text. Named groups `code`, `qty`, `taxable`
   are required; `desc`, `rate`, `mrp`, `cust_code` are optional. A row may continue on the next line.
   A code printed on two lines is captured as `code` plus `code_tail` and joined (Rockman, FCC).
   `taxable` is the value after the row discount and before GST.
   If the same invoice is printed twice in the PDF and the copies are not near-identical, add
   `copy_start`, a regex for the top of each copy, and only the first copy is read (Texspin, Rockman).
   An invoice-level discount goes in `header.discount_total`; the reader checks rows minus that
   discount against the printed subtotal, as the app does.
5. Save it in the supplier's profile. Save refuses a layout that does not compile or lacks a
   required group.
6. **Prove it** before trusting it: parse the invoice and compare every row with a reference —
   the booked Purchase Receipt (item, quantity, net value) or a saved AI reply. The layout must
   reproduce every line. Fitting one invoice is not enough evidence: test a second invoice of the
   same supplier when you have one, and say so when you do not.
7. If printed codes differ from the item master, add Item Code Rules to the same profile. The layout
   reads the code as printed; the rules map it to the Vidira item.

## Learning from the AI

With **Learn Layouts From AI Reads** on, after the AI reads a supplier that has no layout, one
extra text-only AI call proposes a layout. It is saved only if it rebuilds every line the AI read.
It costs a little more per new supplier and never replaces an existing layout.

## Traps seen on real invoices

- **Blank or damaged page.** pypdf raises on a page with no content; the reader treats it as empty.
- **Master typos.** FCC's `7HDRY110CASSY` and `7BPUL150UG4CAASY` are spelled that way in the item master, so the rules map to the misspelling. Fix the master, then the rule.
- **Fused columns.** pypdf can join HSN and quantity (`851180003` is HSN `85118000` and quantity
  `3`). Match the HSN length in the regex: `\d{8}(?P<qty>\d+)`.
- **GST-inclusive Amount column.** Charan Autotech prints Amount = qty × price × 1.18. `taxable`
  must be qty × price. The AI instructions now say this; a layout must do the same.
- **Printed code ≠ item code.** Varroc `CDEI-ACTO-L901A` is item `WCDEIACTOL901A`; Madan Lal `CCHRG4HCAM`
  is `RG4HC`. This is a code rule, not a layout change.
- **Group subtotals** ("Group Wise Total") have no serial number, so a row regex that starts with
  the serial number skips them.
- **Same invoice, several copies.** Original and duplicate pages can double the rows; the quantity
  check catches it and the AI read follows.
- **No GST on the draft.** The inward API books the net value. Compare a draft with the booked
  receipt's **net**, not its grand total.
- **Duplicate guard.** A booked receipt with the same supplier and invoice number blocks a second
  draft. For demos, rename the old receipt's number (keep a backup), never delete it.

## Rules

- Local site first. Do not write to a production site. The non-production migrate step blanks the
  Password fields, so use `reload-doc` for new doctypes and re-enter keys after `bench migrate`.
- Ask before any paid AI call, and say what it costs. A script that scans a file spends money every
  run when the local path is off: call the local reader first and stop if it returns nothing.
- Never print an API key.
