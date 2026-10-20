# Vidira skills

Skills bound to Vidira Innovations (VIPL). They assume its suppliers, Drive folders and ERPNext
site, so they are not part of the general set.

| Skill | What it does |
|---|---|
| `vipl-inwarding` | Supplier-invoice inward chain end to end: email, Drive PENDING folder, warehouse checking CSV, purchase-receipt draft |
| `vipl-purchase-import` | Turns a supplier tax invoice (PDF or INVCEXL xlsx) into ERPNext import files for new items and a purchase receipt |
| `vipl-reorder` | Reorder and purchase-ordering engine: what to buy, how much and when, brand by brand |
| `warehouse-inward-csv` | Converts a supplier inward/GRN invoice into the standard warehouse-inward CSV, one file per invoice |

Link them with `ln -s ~/skillset/skills/vidira/* ~/.claude/skills/`.
