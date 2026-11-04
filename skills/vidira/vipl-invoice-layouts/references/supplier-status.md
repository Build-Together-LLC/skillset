# Supplier status (measured 4 Nov 2026 on vidira.localhost)

Source: the supplier invoice PDFs in the shared `VIDIRA_SUPPLIER_INVOICE_CSV` folder, each compared
with its booked Purchase Receipt. "Code match" is how many receipt items could be found from the
code printed in the invoice text with no rules.

## Layout saved and proven

| Supplier | Proof |
|---|---|
| Varroc Engineering (invoice layout) | 6 of 6 lines map to the booked items; draft net equals the booked net. One invoice only. |
| Shree Amba Industries (Aerostar) | Reproduces all 29 lines of the AI read: same code, quantity and value. Supplier also sends a CSV. |

## Digital PDFs where a layout is the next step

Charan Autotech (17 lines, code match 100%, but the Amount column includes GST), Texspin, Henkel,
Allied Nippon, Freudenberg-NOK, FCC (15 pages), Fiem (noisy OCR text, lower odds).

## Need item code rules as well

HPA Transtrade (`LA-216 HLD-CD` → `216-HLD-CD-`), Madan Lal Bijay Kumar (`CCH(.+)AM` → `\1`,
`CCHPRA7HCAM` → `RA7HC`), Gabriel (`AM-…` → `L…`), Gulati (`FC`/`PT` → `GFC`/`GAE`). These four
are photos or skewed scans, so they are read by the AI and only the code rules apply.

## No usable text layer

Atharva Distributors, Auto Marketing (scan), Vega Auto (6 pages): always the AI read.

Re-measure before relying on this table. It reflects one folder on one date.
