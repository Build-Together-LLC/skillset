# Security and privacy rules for demo documents

- Every key, password, token, phone number and e-mail in the document is an **example**. Say so on the cover (WARNING callout).
- Generate example secrets that look real but are not (random hex of the right length). Never paste a live value,
  even "just for the screenshot". If a real value ever appears in chat or a file, tell the owner to rotate it.
- Screenshots come from **demo data**. QR codes, sessions, tokens and personal data are pixelated.
- Show the **hashed** form where a product supports it (store the hash on the server, the plain key only in the client).
- Document how to **rotate** each secret, in what order, what breaks in between, and how to verify.
- Document the **minimum exposure**: bind containers to 127.0.0.1, HTTPS only, IP allow-list when the caller's IP is stable,
  strong passwords for dashboards, firewall, backups of state folders, least-privilege users.
- Link the vendor's own security page and quote their recommended settings instead of paraphrasing from memory.
- Do not tell a reader to disable TLS verification, open a database or admin port to the internet, or run as root.

## Real data inside auto-filled lists

A demo database still shows real people where the page fills a list by itself. Check these before shooting and after every change of filter:

- chips or buttons that list "people with items", drop-downs that open on focus, search lists that print extra text (hosts, owners),
- the "Assigned To" box and the sidebar of a record, linked-record cards, child tables, dashboard "top" lists,
- settings pages with a contact, owner or fallback e-mail field, and toasts that carry a name.

Hide or rewrite them in the page with an `eval` step before the shot (remove the options that are not demo records, replace text nodes and input
values), or add the rule to a script that runs on every page. Pixelating is a second choice: it shows that something was there.

Then read the text in the pictures. Text in images is not covered by `privacy_scan.py`. A small OCR pass over the screenshot folder with your list of real
surnames and your e-mail domain finds what the eye missed (`pip install rapidocr_onnxruntime` into a scratch virtual environment, never into the
product's environment). `flow-video-builder/scripts/ocr_scan.py` does the same for video and is a working example.
