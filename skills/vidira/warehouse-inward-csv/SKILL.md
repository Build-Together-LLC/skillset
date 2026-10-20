---
name: "warehouse-inward-csv"
description: "Convert a supplier's inward/GRN invoice for VIDIRA (VIPL) into the standardized warehouse-inward CSV the checking team uses — columns item_code, item_name, qty, no_of_boxes, uom, mrp_rate_per_item — one file per invoice named with the invoice number (e.g. 696.csv), saved to the Google Drive \"11 WAREHOUSE INWARDING / STANDARDIZED\" folder. Use this whenever an inward invoice, warehouse inwarding, GRN, or a request to standardize or convert an invoice comes up, for either Shree Amba/Atharva (SPD invoices with pack-slip and invoice-detail CSVs) or Varroc (PDF invoice, MRP pulled from the Varroc master price list). Not for ERPNext purchase-import files (use vipl-purchase-import or guin-purchase-import for those)."
---

# Warehouse Inward CSV

Turn a supplier's inward invoice into the standardized **warehouse-inward CSV** that VIDIRA's (VIPL) receiving/checking team uses to verify goods against the invoice.

## Output — the same for every supplier

One CSV **per invoice**, with exactly these columns and header:

```
item_code,item_name,qty,no_of_boxes,uom,mrp_rate_per_item
```

- **item_code** — the code the warehouse stocks/identifies the part by (supplier-specific, see below). It must be the *complete, correct* code — resolve it from the supplier's master/price list, not blindly from the invoice print (invoices sometimes truncate codes).
- **item_name** — the part description.
- **qty** — total pieces received for that item on the invoice (one row per item; aggregate, do not split per box/scan line).
- **no_of_boxes** — number of individual scanned boxes/bundles for that item. Use 1 unless the source gives a real per-item box count (see Shree Amba).
- **uom** — the real unit of measure (NOS, SET, NO…) from the invoice — NOT a packing / "type of box" code.
- **mrp_rate_per_item** — the real MRP (integer). Never invent it or copy a sample's noise; pull it from the actual invoice or the supplier's price list.

**File name:** the invoice serial number only, e.g. `696.csv`, `6307712989.csv`. No prefixes, no "Warehouse Inward", no leading zeros for the short Shree Amba serials.

**Save to:** the Google Drive **"11 WAREHOUSE INWARDING / STANDARDIZED"** folder, **Drive only** (do not also copy to a local folder). If you can't find the folder, search Drive for the title containing WAREHOUSE INWARDING, then its STANDARDIZED subfolder; create STANDARDIZED if missing.

**Always verify** before saving: the sum of qty across your rows must equal the invoice's printed total quantity. If it doesn't, you've mis-parsed — stop and fix it. This one check catches almost every extraction bug.

---

## Identify the supplier first

- **Shree Amba Industries / Atharva** — invoice numbers like 26-27/SPD/000696; item codes are AS-### / ARF-###. Comes as a folder with a PACK_SLIP.CSV, an INVOICE_DTL.CSV, and a PDF. Use the **Shree Amba path**.
- **Varroc Engineering** — GSTIN 27AAACV2420J1ZI; invoice numbers are 10 digits like 6307712989; two codes per line (a part code like FCAP-APCH-01AZ and a numeric K-code). Comes as a PDF only. Use the **Varroc path**.

If it's a different supplier, apply the same output spec: map their columns to item_code / item_name / qty / uom / MRP, boxes=1 unless a real count exists, validate qty against the invoice total, and ask the user which of their codes is the stock item_code and where MRP comes from if the invoice has none.

---

## Shree Amba / Atharva path

Build everything from the two CSVs (both use **latin-1** encoding — they contain stray 0xA0 bytes).

- Rows and qty/uom/mrp come from **INVOICE_DTL** (columns: SL.NO, Invoice No, Product Code, Products Desc, UOM, Inv. QTY, Price, Discount, Amount, MRP RATE, …). One row per item already.
  - item_code = Product Code (idx 2), item_name = Products Desc (idx 3), qty = Inv. QTY (idx 5), uom = UOM (idx 4, NOS/SET), mrp_rate_per_item = MRP RATE (idx 9).
- **no_of_boxes** comes from the **PACK_SLIP** (columns: SCAN CODE, PRODUCT CODE, DESCRIPTION, QTY, NO OF BOX, TYPE OF BOX). Count the number of scan-code lines for each Product Code — that's how many physical boxes/bundles arrived for that item. Do NOT use the "TYPE OF BOX" column (that's "MS", a packing type, not the UOM). Do NOT use the "NO OF BOX" column (that's a running carton index).
- Keep the invoice-detail row order.

Mistakes that were made and corrected — avoid them:
- Building from the pack slip instead of the invoice detail gives one row per scan line, "MS" as UOM, and wrong box numbers. The invoice detail is the source of truth; the pack slip only supplies the box *count*.
- Hard-coding no_of_boxes=1 leaves the checking team unable to verify. Use the real scan-line count.

Verify: per-item qty and MRP reconcile to INVOICE_DTL; total qty matches the invoice.

---

## Varroc path

Varroc invoices are multi-column PDFs with no MRP on them. Extract line items from the PDF, then use the Varroc master to get both the correct part code and the MRP.

**uom** on these is NO. **no_of_boxes = 1** (these invoices carry no per-item box count).

**item_code = the master PART No., resolved via the K-code (New SAP Code) — NOT the invoice's printed part code.** This matters: Varroc invoices sometimes print the part code truncated, e.g. `FPMT-CDLX-`, `MGCP-ATVA-`, `OSEAL-SSPRT-` with the final segment cut off. Each line's numeric K-code is reliable, so look the K-code up in the master to get the full PART No. (e.g. K354105400 → `FPMT-CDLX-AAF4M`). Fall back to the invoice's printed part code only if the K-code isn't in the master. A quick tell that you need to resolve: any item_code ending in a hyphen is truncated.

### Parsing the PDF (pdfplumber, column x-bands)

Use word x-positions, not naive text splitting (descriptions wrap and the sales-rate sits one row above the item line). Anchor each item on its code and validate the total. Capture the **K-code** on each row (it's the code-column token right of the part code) — you need it for the code+MRP lookup.

```python
import pdfplumber, re
from collections import defaultdict
KRE = re.compile(r'^K[0-9A-Z]{5,}$')   # K-codes can contain letters, e.g. K1050062MK, K353A36000

def parse_varroc(pdf_path):
    items = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            lines = defaultdict(list)
            for w in page.extract_words():
                lines[round(w['top'])].append(w)
            tops = sorted(lines)
            kc = lambda row: [w for w in row if 100 <= w['x0'] < 170 and KRE.match(w['text'])]
            anchors = [t for t in tops
                       if any(x['x0'] < 32 and x['text'].isdigit() for x in lines[t]) and kc(lines[t])]
            for i, at in enumerate(anchors):
                nt = anchors[i+1] if i+1 < len(anchors) else 10**9
                bound = min(nt, at + 27)
                L = lines[at]
                part = next((w['text'] for w in L if 35 <= w['x0'] < 100), '')
                k = kc(L)[0]['text']
                q = [w for w in L if 250 <= w['x0'] < 300 and re.match(r'^[\d,]+$', w['text'])]
                qty = int(q[0]['text'].replace(',', '')) if q else None
                desc, STOP = [], {'Total','Taxable','IGST','Rupees','Paise','Words','Net','Grand','HSN',
                                  'Transport','Prepared','Checked','Authorised','Page','Interest','Invoice','Amt'}
                stop = False
                for t in tops:
                    if stop: break
                    if at < t < bound:
                        for w in sorted(lines[t], key=lambda z: z['x0']):
                            tx = w['text'].strip()
                            if tx in STOP: stop = True; break
                            if 105 <= w['x0'] < 262 and not re.match(r'^\d{8}$', tx) and tx not in ('NO','By',''):
                                desc.append(tx)
                items.append({'part': part, 'k': k, 'qty': qty, 'uom': 'NO', 'desc': ' '.join(desc)})
    return items
```

Traps that cost real errors here (all handled above, keep them):
- **Truncated part codes on the invoice** (`FPMT-CDLX-`) — resolve item_code from the master by K-code, as above. This was a real defect: codes were saved cut off because they were taken from the invoice print.
- **K-codes with letters** (K1050062MK) and odd wrapped rows: anchoring on digits-only would silently drop those items and the qty total comes out low. Use `^K[0-9A-Z]{5,}$`.
- The **sales rate sits about 2px above** the item's main line; qty is the integer in x-band ~255–300 on the anchor line.
- **Description over-run:** on the last item of a page the footer ("Total…", "…Rupees…") leaks into the description — stop at the STOP words and cap to a couple of wrapped lines.
- Confirm sum(qty) equals the invoice's printed "Total" quantity (and for multi-page invoices, cross-check the HSN-summary quantity total).

### Master lookup — part code + MRP

The Varroc master workbook (title like **"Order format VARROC.xlsx"** in Drive — search the title for Varroc; if several exist use the newest version) has several sheets (Order Format, ABS Parts Order Format, 4 Wh. Order Format, 4 Wh. Hiker). In each, column **New SAP Code** is the K-code, **PART No.** is the full part code, and there's an **MRP** column. Build two lookups across all sheets keyed by K-code: `{K -> PART No.}` and `{K -> MRP}` (also keep `{PART No. -> MRP}` as a secondary). For each invoice item: item_code = `K -> PART No.` (fallback to invoice part); mrp = `PART No. -> MRP` or `K -> MRP`. Report any item with no master match rather than leaving it silently blank or truncated.

---

## Saving to Drive, and its limitations

- Upload with the Google Drive connector's create-file, contentMimeType text/csv, disableConversionToGoogleType true, into the STANDARDIZED folder.
- The Drive connector **cannot rename, overwrite, or delete**. So:
  - Name files correctly the first time (invoice number .csv).
  - To replace/remove files (a bad earlier version, or a rename), use the **Claude-in-Chrome** browser tools on drive.google.com: select the row then trash icon (or Delete key) to trash; select then pencil icon then retype name then OK to rename. Target the exact file to avoid hitting the wrong duplicate.

## Quick self-check before you finish
1. One row per item, aggregated. 2. Columns/header exactly as specified. 3. qty total equals invoice total. 4. uom is the real unit (NOS/SET/NO), not a packing code. 5. Every item_code is complete (none ending in a hyphen) — Varroc codes resolved from the master via K-code. 6. MRP populated for every row. 7. File named with the invoice number, saved to STANDARDIZED on Drive.

