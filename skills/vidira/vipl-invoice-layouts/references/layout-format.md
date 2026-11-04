# Layout format

A layout is JSON stored in `Supplier Invoice Profile.layout`.

```json
{
 "detect": ["For Varroc Engineering", "Varroc Part code"],
 "date_format": "%d.%m.%Y",
 "header": {
  "supplier_gstin": "GSTIN\\s*:\\s*(27AAACV2420J1Z\\w)",
  "document_no": "Invoice No\\s*:\\s*(\\d+)",
  "document_date": "Invoice Date\\s*:\\s*([\\d.]+)",
  "subtotal": "Net Value\\s+([\\d,.]+)"
 },
 "row": "^\\s*\\d+\\s+(?P<code>...)\\s+...(?P<qty>\\d+)\\s+...(?P<taxable>[\\d,]+\\.\\d+)..."
}
```

| Key | Meaning |
|---|---|
| `detect` | List of regexes. The layout applies only when **all** match somewhere in the text. |
| `date_format` | strptime format of `document_date` (`%d-%b-%Y` reads `31-MAR-2026`). |
| `header` | Field → regex with **one** capture group. Fields: `supplier_name`, `supplier_gstin`, `document_no`, `document_date`, `subtotal`, `tax_total`, `grand_total`, `total_qty`. Numbers keep printed commas; a trailing `-` is dropped. |
| `row` | One regex, run with `re.M` over the whole text. Required groups `code`, `qty`, `taxable`. Optional `desc`, `rate`, `mrp`, `cust_code`. |

Output has the same shape as the AI reply, so matching, MRP, totals and the draft receipt work
unchanged: `document_type` is `tax_invoice`, `confidence` 100, lines carry
`code, cust_code, desc, qty, rate, mrp, taxable`.

Python regexes. Escape backslashes in JSON. The profile refuses to save a layout that is not valid
JSON, has a regex that does not compile, or has a `row` without `code`, `qty` and `taxable`.
