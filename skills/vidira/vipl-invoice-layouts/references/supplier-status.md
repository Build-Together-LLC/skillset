# Supplier status (measured 4 Nov 2026 on vidira.localhost)

Source: the supplier invoice PDFs in the shared `VIDIRA_SUPPLIER_INVOICE_CSV` folder, each compared
with its booked Purchase Receipt. Re-measure before relying on this: it is one folder on one date.

## Layout saved and proven (read locally, US$0)

| Supplier | Lines | Proof against the booked receipt |
|---|---|---|
| Varroc Engineering (invoice layout) | 6 | 6/6 items, draft net equals booked net. One invoice only. |
| Shree Amba Industries (Aerostar) | 29 | Reproduces all 29 lines of the AI read. |
| Rockman Industries | 3 | 3/3 items and quantities, net within ₹0.30 |
| Texspin Bearings | 2 | 2/2, net exact (needs one code rule) |
| SAP Swiss Solutions | 44 | 44/44, net within ₹0.23 (one code rule) |
| FCC Clutch India | 26 | 26/26, net exact (12 code rules, two for master typos) |
| Remsons Industries | 40 | No booked receipt for this 2023 invoice. Printed total quantity and taxable value both match, 39 of 40 items matched, 1 for confirmation. |

Each ran end to end on the Scan Invoice path with Provider "Local layout", 0 tokens, and a draft
Purchase Receipt. Run over all 53 PDFs, the reader took exactly these seven and rejected the rest,
so no scan was misread as another supplier. Each layout was fitted to one invoice per supplier;
a second invoice of the same supplier is the next proof.

## Cannot be read locally

- **Camera scans (Adobe Scan, intsig):** Charan Autotech, HPA Transtrade, Madan Lal Bijay Kumar, Gabriel,
  Gulati, Freudenberg-NOK, Henkel, Allied Nippon, Fiem, Osram, Avon, Naveen, Janta, King Quality,
  Resil, Pricol, International Agencies, Jesco, Sahil, Mebesto, Ucal, Bando and the rest. Always the AI read.
  Item code rules still apply to them (Gabriel, Gulati, HPA, Madan Lal have rules on vidira.localhost).
- **No item code printed:** Vega (TallyPrime) prints a description only, so the matcher has no code.
- **Not a tax invoice:** Niterra and ANL are proforma invoices.
