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
