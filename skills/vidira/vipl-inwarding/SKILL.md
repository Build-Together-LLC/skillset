---
name: "vipl-inwarding"
description: "VIPL's supplier-invoice inward chain, end to end — invoices arrive by email and auto-save to the Drive PENDING folder, then become the warehouse checking CSV and an ERPNext purchase-receipt draft. Use whenever a new supplier invoice lands, someone says an invoice arrived in Gmail or the Drive folder, or asks to process/inward/book an incoming invoice for VIDIRA / VIPL. NO Gmail connector is needed — always look in PENDING first."
---

# VIPL — supplier invoice inward chain

Turns an incoming supplier invoice into the two things VIPL needs: the **standardised CSV the
warehouse checking team scans against**, and an **ERPNext purchase-receipt draft**. For
**VIDIRA INNOVATIONS PVT LTD (VIPL)**, Burdwan, on ERPNext V16.

## Three rules before anything else

**1. All times are IST (UTC+5:30). The shell reports UTC — always convert** (`TZ=Asia/Kolkata
date`). A file the shell lists at 09:35 arrived at **15:05** for Viren. Quoting UTC has already
put an invoice on the wrong day.

**2. One chat at a time.** Two sessions on the same PENDING folder can book an invoice twice.
Before creating any GRN, check ERPNext for an existing draft with the same supplier and invoice.

**3. Do not ask what you can look up.** The file in PENDING names the supplier. The outputs are
always the checking CSV, the warehouse upload and the ERPNext draft. Company, warehouse, folders
and the API key are all in memory. Read, then act.

## Start here — do NOT ask for a Gmail connector

**You do not need mailbox access.** A Google Apps Script copies supplier attachments into a
Drive folder that is connected as a normal folder. When Viren says *"an invoice landed in
Gmail"*, look in:

```
My Drive/VIPL CoWork/11 WAREHOUSE INWARDING/PENDING/
```

Newest files by modification time are the new invoice. If PENDING has nothing new, the script
runs on a 15-minute timer — wait, or ask Viren to press **Run** in the Apps Script editor.
Drive sync to the local folder lags a couple of minutes.

## How the mail gets there

Zoho forwards everything sent to `accounts@vidira.in` to `vidiradrive@gmail.com` (Viren,
30-Aug-2026: *"let all the emails come to the drive, u handle it from there"*). The Apps Script
project **"VIPL - save supplier invoices to PENDING"** runs there every 15 minutes, saving
`csv, pdf, xls, xlsx` attachments from the senders in `SENDERS` and labelling each thread
`invoice-saved`.

**When an invoice does not arrive, it is almost always the `SENDERS` list.** Add the supplier's
**domain** — not a person, not a subject pattern. Learned twice in one evening: Varroc was
matched on the subject `Invoice-63`, their numbering moved to the 65-series, and no Varroc
invoice auto-saved at all (15.7% of purchases). FCC (₹127.6 L/yr) had never been in the list
either.

Senders as of 31-Aug-2026: `varroc.com`, `fcc-india.com`, `saigroupglobal.com` (Shree Amba),
`alliednippon.com`, `unominda.com`, `pricol`, `vegaauto`.

Editing the script is a **standing rule in Viren's Google account — get his go-ahead each
time.** Editor is Monaco: `monaco.editor.getModels()[0].setValue(...)`, then **click the save
icon** and confirm "Saved to Drive" (Ctrl+S usually misses focus). Reading the model back may be
blocked as cookie-like data — edit blind, return a short status string.

The mailbox now holds a copy of the whole business inbox, and Gmail and Drive share 15 GB. If it
fills, Drive stops accepting files and the CoWork folder silently breaks.

## Step 1 — the checking CSV

Use the **`warehouse-inward-csv`** skill. One file per invoice, named with the invoice serial
only (`933.csv`, `6505331065.csv`, `1010176581.csv`), into
`11 WAREHOUSE INWARDING/STANDARDIZED/`, columns exactly:

```
item_code,item_name,qty,no_of_boxes,uom,mrp_rate_per_item
```

**The check that catches nearly every parsing bug: qty must sum to the invoice's printed
total**, and line serials must run 1…n with no gap. If either fails, stop.

- **Shree Amba / Atharva** — rows, qty, uom, MRP from `INVOICE_DTL.CSV`; `no_of_boxes` = count of
  scan lines per product code in `PACK_SLIP.CSV`. Both latin-1.
- **Varroc** — PDF only, no MRP. Resolve **item_code and MRP from the Varroc master by K-code**,
  never from the invoice print, which truncates codes (`FPMT-CDLX-`). Master:
  `06 SUPPLIER ORDER FORMATS/Varroc/Order format <Month Year> - Version-NN.xlsx`, header row 3,
  columns `New SAP Code`, `PART No.`, `MRP`. Any item_code ending in a hyphen means the lookup
  was skipped.
- **FCC** — **the PDF holds five copies of the same invoice** (Original, Duplicate for
  Transporter, Triplicate, Acknowledgement, Extra): a 6-line invoice is 10 pages. **Parse page 1
  only** or you book five times the goods. MRP from
  `06 SUPPLIER ORDER FORMATS/FCC/AFM New Price List Effective from 1st Apr 2026 Domestic.xlsx`
  (header row 3). Extracted text runs qty into the HSN (`8714109032.000` = HSN 87141090 + qty 32).
- **VEGA** — helmets, size-wise codes (`VGA46AA-XL`). The invoice spells colours out where the
  item master abbreviates (BLACK RED / `BK/RED`, DULL BLACK / `DBK`, BLACK ORANGE / `BK/ORNG`),
  and discounts at **invoice level, not per line**. MRP source and how to apply that discount
  are **not yet settled — ask Viren.**

The STANDARDIZED CSV carries the **supplier's own part code** for Varroc, FCC and VEGA (that is
what the team scans), not VIPL's item code.

## Step 2 — upload to the warehouse app

etabyte Django admin, `warehouse-admin-v2.etabyte.tech`. **This is the step that gets
forgotten.** Multipart POST from a page on that origin (cross-origin fetch fails):

```js
const tok = document.querySelector('input[name=csrfmiddlewaretoken]').value;
const fd = new FormData();
fd.append('csrfmiddlewaretoken', tok);
fd.append('warehouse', '10');          // WH-MAIN - VIPL   (12 = WH-SILIGURI)
fd.append('suppliers', 'SUPP-00037');  // Shree Amba · 00044 Varroc · 00009 FCC · 00045 Vega
fd.append('csv_files', new File([csv], '<invoice>.csv', {type:'text/csv'}));
await fetch(location.href, {method:'POST', body:fd, credentials:'same-origin'});
```
at `/warehouse-admin/admin_models/invoice/upload-invoice/`. Verify with
`/warehouse-admin/admin_models/inwardinvoiceitem/?q=<invoice no>`.

A **new supplier** needs a *Brand field identifiers* record first
(`/warehouse-admin/admin_models/brandfieldidentifiers/add/`), mapping that supplier's **printed
invoice column headings** to the app's fields. Two non-obvious rules: **uom is a heading when the
invoice has a UOM column and a literal constant (`PCS`, `NOS`) when it doesn't**; order
confirmation number is used only by Varroc (`CUSTOMER PO`). There is no separate supplier
master — this record *is* the supplier.

## Step 3 — the ERPNext purchase receipt

Build **from the invoice, not from the scan** (Viren's explicit choice). `vipl-purchase-import`
has the file format. Two delivery routes, both used:

**A. Import file** → `10 PURCHASE IMPORT/VIPL Purchase Receipt - <SUPPLIER> <INVOICE>.csv`:

```
Supplier,Date,Currency,Exchange Rate,Item Code (Items),Accepted Quantity (Items),UOM (Items),
HSN/SAC (Items),Price List Rate (Items),Discount on Price List Rate (%) (Items),
MRP (Items),Selling Rate (Items),Accepted Warehouse (Items)
```
Parent values on the first row only. No tax rows, no batch column, no separate Item Price file.

**B. Draft by API** (`docstatus: 0`, **never submit** — Viren submits). Fieldnames:
`custom_mrp`, `custom_selling_rate`, `price_list_rate`, `discount_percentage`, `warehouse`,
`use_serial_batch_fields`. Company `VIDIRA INNOVATIONS PVT. LTD.`, `naming_series`
`MAT-PRE-.YYYY.-`, `buying_price_list` `Standard Buying`, `taxes_and_charges`
`Input GST Out-state - VIPL` with one `On Net Total` row on `GST008 - Input Tax IGST - VIPL` at
rate 0. URL-encode the doctype: `/api/resource/Purchase%20Receipt`.

**Rate vs discount — mutually exclusive.** Set `discount_percentage` and ERPNext recomputes the
rate, rounding the percentage to one decimal (cost ₹1.64 on one invoice). Set `rate` +
`discount_amount` and the money is exact but Discount % reads 0. **Viren chose the percentage.**
Warn that the auto-raised Purchase Invoice will then differ from the supplier's by a rupee or two.

Per-supplier pricing — copy the last file for that supplier:
- **Shree Amba** — `Price List Rate = MRP`, discount = combined `1 − amount/(qty×MRP)`, MRP and
  Selling Rate = MRP.
- **Varroc** — `Price List Rate = invoice sales rate`, discount `5`, MRP/Selling = master MRP.
  Item codes are **VIPL's own**, via `01 MASTERS/Supplier Code Mapping - VARROC.xlsx`.
- **FCC** — `Price List Rate = MRP`, discount derived. Item code = **`7` + FCC part code, minus
  `FCC-`, minus `-ORG`, hyphens and dots removed** (`FCC-Y-FZ-153-C.ASSY-ORG` → `7YFZ153CASSY`);
  verify in `01 MASTERS/Supplier Code Mapping - ALL BRANDS.xlsx`, sheet `Mapping`.

## Batches and MRP — two things NOT to raise

**Batches create themselves.** ERPNext generates `{MRP}-{ITEM_CODE}` from `custom_mrp` **when
the receipt is submitted**. A draft shows `batch_no: None` on any line whose MRP is new — that is
normal, not a blocker. Verified 31-Aug on submitted GRN/2627/01040, every line batched.
**Put the right MRP on the line and say nothing about batches.**

**Never change an item's MRP.** If the invoice or price list disagrees with ERPNext, **report it
and stop.** Do not raise it, lower it, or build an update file unless Viren asks. The receipt
line still carries the invoice MRP so the batch is correct; the item master is his to change.

## Reconciliation, once the team has scanned

Six checks: qty short, qty over, **MRP mismatch**, mixed MRP on one code, on the invoice but not
scanned, scanned but not on the invoice. Over-shipment on Shree Amba is usually pack rounding.

## Housekeeping

Move a booked file set to `11 WAREHOUSE INWARDING/DONE/`. Filenames must be **Windows-safe**
(no `< > : " / \ | ? *`, no trailing dot or space). Invoice dates are not arrival dates: Shree
Amba transit to Burdwan runs about 8 days, 12 at p90 — a recent unreceived invoice is normal.

