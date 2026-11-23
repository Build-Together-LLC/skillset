# Vidira skills

Skills bound to Vidira Innovations (VIPL). They assume its suppliers, Drive folders and ERPNext
site, so they are not part of the general set.

| Skill | What it does |
|---|---|
| `vipl-inwarding` | Supplier-invoice inward chain end to end: email, Drive PENDING folder, warehouse checking CSV, purchase-receipt draft |
| `vipl-purchase-import` | Turns a supplier tax invoice (PDF or INVCEXL xlsx) into ERPNext import files for new items and a purchase receipt |
| `vipl-reorder` | Reorder and purchase-ordering engine: what to buy, how much and when, brand by brand |
| `vipl-invoice-layouts` | Reads a known supplier's invoice PDF from a saved layout with no AI cost, falls back to the AI, and writes new layouts; seven proven layouts (Varroc, Shree Amba, Rockman, Texspin, SAP Swiss, FCC, Remsons) |
| `warehouse-inward-csv` | Converts a supplier inward/GRN invoice into the standard warehouse-inward CSV, one file per invoice |
| `vidira-site-setup` | Builds a fresh `vidira.localhost` on a local Frappe v16 bench (macOS): v16 check, GitHub login, clone + install the 11 Vidira apps on their branches, build, migrate, verify, stop the bench. Python script, plain terminal commands and an AI prompt; optional steps restore a Frappe Cloud backup and empty log tables (never transactions or master data). Holds the shared engine used by the two skills below |
| `autorider-site-setup` | Same workflow for `autorider.localhost` (payments, hrms, india_compliance, vidira_group, frappe_whatsapp, pos_next). Thin launcher over `vidira-site-setup` |
| `guin-site-setup` | Same workflow for `guin.localhost` (payments, india_compliance, taraknath, pos_next). Thin launcher over `vidira-site-setup` |

Link them with `ln -s ~/skillset/skills/vidira/* ~/.claude/skills/`.

The three `*-site-setup` skills belong together: `autorider-site-setup` and `guin-site-setup` call the script in `vidira-site-setup`, so keep all three (they are siblings here). Each has a `README.md` that works without AI.
