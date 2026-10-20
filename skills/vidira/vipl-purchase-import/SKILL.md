---
name: "vipl-purchase-import"
description: "Turn a supplier tax invoice billed to VIDIRA INNOVATIONS PVT LTD (PDF or INVCEXL xlsx export) into VIPL's own ERPNext import files — new items (which carry their prices) and a purchase receipt. Use whenever a VIPL supplier invoice, despatch, GRN or purchase import comes up (UNO Minda, NBC, Varroc, etc.). Not for GUIN — that has its own skill."
---

# VIPL purchase import — supplier invoice to ERPNext

Turns a **supplier's tax invoice** (billed to VIDIRA INNOVATIONS PRIVATE LIMITED)
into the files **VIPL imports into its own ERPNext**. A *purchase* into VIPL, not a
sale. Not the same as `guin-purchase-import` (that builds files for GUIN, a customer).

**Be careful.** Every mistake lands in live stock and live prices. Reconcile against
the printed invoice at every step and say plainly when a number does not tie.

## What is DIFFERENT from Guin — VIPL's automations (do NOT emit these)

1. **Item Prices auto-create from the item.** The new-items file already carries
   `MRP`, `Standard Buying Rate`, `Standard Selling Rate` per row; ERPNext generates
   the Item Price records from them. **Do NOT produce a separate Item Price file** —
   it would double-import and throw "Item Price appears multiple times".
2. **Batch numbers auto-assign on receipt** — never emit batch columns.
3. **The Purchase Invoice auto-raises from the receipt** — build only the receipt,
   with **no tax rows** (the auto-PI applies the tax template). No PI file.

So VIPL produces just **TWO files**: new items (prices baked in) and purchase receipt.

## Working folder (`My Drive/VIPL CoWork`)

```
01 MASTERS/                 Item MASTER.xlsx   (new-vs-existing; sheet Item, key ID)
                            Company Landing 2026-27 v*.xlsx  (margin calculator)
                            SPARK MINDA WH - OE REF and REF NO.xlsx  (OE/Ref lookup)
06 SUPPLIER ORDER FORMATS/  supplier price lists + catalogues (MRP + OE ref source)
10 PURCHASE IMPORT/         put the output files here
```
Read xlsx with `engine="calamine"` (pip install python-calamine first).
Item MASTER has ~68k rows: `ID` (=Item Code, join key), `Item Name`, `Description`,
`Brand`, `Sub Brand`, `HSN/SAC`, `MRP`, ... Existing items already carry MRP + Sub
Brand — reuse them, do not recompute or re-price them.

## VIPL's ERPNext settings

| | |
|---|---|
| Company | `VIDIRA INNOVATIONS PRIVATE LIMITED` (abbr `VIPL`, state WB 19) |
| Item Group | `Products` (Minda), `Bearings` (NBC), … |
| UOM | `PCS` (Minda). Map invoice `NOS`→`PCS` |
| Item Tax Template (Taxes) | `GST 18% - VIPL` |
| Warehouses | `WH-MAIN` (Burdwan), `WH-SILIGURI` — confirm the exact ERPNext name |
| Price lists (auto from item) | `MRP`, `Standard Buying`, `Standard Selling` — all set to MRP |

IGST if the invoice carries IGST (supplier outside WB, e.g. Minda/Haryana 06);
CGST+SGST if intra-state. Receipt has no tax rows either way — just report the mode.

## MRP source — the supplier PRICE LIST, not the invoice, not the old catalogue

For UNO MINDA use `06 SUPPLIER ORDER FORMATS/UNO minda*Master Price List*.xlsx`
(header on row 3): `PART NO, DESCRIPTION, APPLICATION, MOQ, GST%, TD% W/O GST,
HSN Code, MRP`. Current & authoritative — prefer it over the `2W Electrical/
Mechanical Catalogue.pdf` (older, stale MRPs).

**Validation that ties everything:** invoice **Unit Rate = MRP × (1 − TD%)** exactly
(SW-0562 63×(1−0.41)=37.17; TD-5056U 335×(1−0.47)=177.55). Compute per line and
confirm — if it doesn't tie, the MRP or TD% is wrong. Set `MRP = Standard Buying =
Standard Selling = list MRP`; the buying discount is on the receipt, the selling
discount in pricing rules — never bake either into the item rate. `Company Landing …
.xlsx` sheet `Uno Minda` shows per-category TD and the customer "Basic Discount"
(Switches 28%, HLT/Blinker 33%) applied by those rules — margin reference only.

## Item Code, Sub Brand, and NAME/DESCRIPTION policy

Item Code = supplier part number **as-is** (Minda). Brand = `UNO MINDA` (real name).

**Sub Brand is mandatory and by product category** (pricing keys on Sub Brand ×
customer group — a wrong one sells at the wrong price):

| Product (part prefix / description) | Sub Brand |
|---|---|
| Switch / HBS / panel / lever assembly (`SW-*`, `MI-*`) | `UNO SWT` |
| Indicator / blinker (`TD-*`) | `UNO BLKR` |
| Lighting: tail-light lens/unit, headlight (`6xxx-615`, `RT-*`, `TL-*`) | `UNO HLT` |
| Horn unit (not horn switch) | `UNO HORN` |

**Two name fields, house style, NO brand suffix (the Brand field carries it):**

- **Item Name** = terse ALL-CAPS house code. Learn the exact abbreviations from
  existing same-type items in Item MASTER before naming. Patterns:
  - HBS (Handle Bar Switch) = our Combination Switch → `COM.SWCH <LH/RH> <KS/SELF> <MODEL> <SPEC>` (KS=Kick Start, SELF=Self Start; LH=Left Hand, RH=Right Hand)
  - Panel switch (e.g. NTorq) → also `COM.SWCH RH NTORQ BS6 …`
  - Horn switch → `HORN SWCH <YEL> <MODEL>` (distinct from a horn UNIT, which is Sub Brand UNO HORN)
  - Engine stop/start switch → `ENG STOP/START SWCH <MODEL>`
  - Tail-light lens/glass → `T.L.GLASS <MODEL>` ; tail-light unit/assembly → `T.L.ASSLY <MODEL>` ; headlight → `H.L.ASLY <MODEL>`
  - Indicator → `IND.<...> <MODEL>` ; abbrevs SPLDR=Splendor, GLMR=Glamour, PUL=Pulsar, NTORQ=NTorq, SCTY=Scooty, SPCTRA=Spectra, (U)=Universal
- **Description** = the same, expanded to Title Case (e.g. `Combination Switch Right
  Hand Kick Start Centra`, `Tail Light Glass Splendor NXG`). Use the price list's
  DESCRIPTION + APPLICATION as source text.

### OE reference and supplier ref no. — always append to the Description

Owner decision, 05-Sep-2026. Whenever the price list, catalogue or invoice gives an
**OE/OEM number** (the vehicle maker's part number) or the supplier's own **REF.NO /
alternate code**, put them at the **end of the Description**, in this exact shape:

```
<readable description> | OE: <oe> | Ref: <ref>
<readable description> | OE: 32100-KWH-970S / 32100-KWH-9700 | Ref: 0209DF
```

- Multiple OE numbers joined with ` / `. Drop the `OE:` or `Ref:` tag entirely when
  the source gives none — never write an empty tag or a `-`.
- Never put it in the Item Name and never invent a custom field. The Description is
  the only place agreed.
- **Why it must be the Description:** the order app's search index is
  `description + name + code + brand + group + sub-category + part name`, so anything
  in the Description is instantly searchable by the sales team, and the Description is
  what prints under the item name on the app card. Retailers ask for parts by the OE
  number stamped on the old part, not by our code.
- Strip a ref that is already loosely embedded in the old description (e.g. a trailing
  `, 0212sk`) before appending the clean tags, so it does not appear twice.
- Started as a Spark Minda wiring pilot (92 items, Dec-25 catalogue); extend to any
  brand whose catalogue carries the numbers. The Spark Minda lookup lives in
  `01 MASTERS/SPARK MINDA WH - OE REF and REF NO.xlsx` (sheet `Full catalogue Dec-25`,
  466 rows) — check it before creating any `WH-` item.

When a part type has no house precedent under the brand, or the model/fitment is
unclear, **ask the owner** — don't guess. (Owner-confirmed examples: SW-0562 is an
Engine Stop/Start Switch not a brake switch; SW-0657N model = Centra.)

## The two files

**1. New items** (`Item`, Insert New Records) — carries the prices:
`Item Code, Item Name, Description, Item Group, Default Unit of Measure, Brand,
Sub Brand, HSN/SAC, MRP, Standard Buying Rate, Standard Selling Rate, Maintain Stock,
Item Tax Template (Taxes)`. MRP=Buying=Selling = list MRP. HSN from the price list.
New items only (existing codes already priced — leave them alone).

**2. Purchase receipt** (`Purchase Receipt`, Insert New Records) — every invoice line
(new and existing). Flat file, parent on first row only (`Supplier, Date, Company,
Currency, Exchange Rate, Set Target Warehouse, Supplier Invoice No, Supplier Invoice
Date` — no Series, no tax rows); child rows ` (Items)`: `Item Code, Accepted Quantity,
UOM, UOM Conversion Factor, Price List Rate, Discount on Price List Rate (%), Rate,
Accepted Warehouse, HSN/SAC`.
- Price from the invoice: `Rate = Taxable Value / Qty`, `Price List Rate = Unit Rate`,
  derive `Discount % = (1 − Rate/Unit Rate) × 100`. **Do not trust the invoice
  `Disc Rate` column** (shows 0% on lines that are actually discounted); taxable value
  is authoritative, so `Price List Rate × (1 − disc) = Rate` holds. Verify.
- No batch, no tax rows, no PI.

Import order: New items → Purchase receipt. Then VIPL auto-creates the Item Prices,
auto-raises the PI, and assigns batches.

**An existing item whose OE/Ref is newly available** does not belong in the new-items
file. Deliver it as a separate `Item → Update Existing Records` CSV with just
`ID, Description`, so live prices and stock are untouched.

## Always report

lines / qty / taxable / tax / grand total and the tie; IGST vs CGST/SGST; new vs
existing count; any line where `MRP×(1−TD) ≠ Unit Rate` or `PLR×(1−disc) ≠ Rate`;
any new item with unresolved MRP or Sub Brand or an uncertain house name;
**how many new items carry an OE ref and how many the source had none for**.

## Helper script

`vipl_invoice_to_vipl.py` (in `VIPL CoWork/10 PURCHASE IMPORT/`) does the receipt
end-to-end and the new-item split given the master + a `{part: MRP}` map.
`--receipt-only` needs neither. Extend `SUPPLIERS` + the sub-brand map for new
suppliers. (It can still emit a standalone prices file, but VIPL does NOT use it —
prices come from the item.)

