# Projects — Hybrowlabs defaults (example snapshot)

**`projects.csv` next to this file is a snapshot of `operate.hybrowlabs.com`.** It validates
project IDs only when the profile's site is that host and no refreshed cache exists. On any other
Frappe site run `catalogue refresh`: it caches the Open projects the login can see, and
`catalogue list --type project --match <text>` resolves a name to the exact Project ID
(see `references/catalogue.md`; the list is limited by the user's permissions, and without a cache
project IDs are not checked offline).

`project` on `Timesheet Detail` is a **Link field to the Project doctype — it stores the Project's
docname (ID), which is the "Project ID" column, NOT the short code you see in the list view.**
Getting this wrong makes Frappe reject the row, so always take the value from the **Project ID**
column of the active catalogue.

## Hybrowlabs specifics

For most Hybrowlabs client projects the ID happens to be the descriptive name (e.g. `IIM Bangalore`,
`UnityERP`). For the two internal/Walnut projects the ID is an auto-generated `PROJ-####` code and
the descriptive label lives in the short code instead:

- Walnut School → ID `PROJ-0019`
- General Work → ID `PROJ-0002`

---

## Default project

The default project is **saved in the profile** the first time the skill runs (Step 0) and reused on
every later run. Use it for every entry unless the user hints at a different project for a
particular update or entry.

On the Hybrowlabs site, **`PROJ-0019` (Walnut School)** is only a suggestion for someone setting up
their profile who doesn't know their Project ID — confirm it with them rather than assuming it. On any
other site there is no suggested default: ask, and resolve it with `catalogue list`.

```json
"project": "PROJ-0019",
"project_name": "Walnut School"
```

Set `project_name` to the short code / display name (Frappe fetches it automatically, so a
mismatch here is only cosmetic — but keep it consistent).

---

## Hybrowlabs project master (bundled `projects.csv`)

| Project ID (`project`) | Short Code (`project_name`) | Status | Company |
|---|---|---|---|
| `PROJ-0019` | Walnut School | Open | Hybrowlabs Technologies Pvt Ltd |
| `PROJ-0002` | General Work | Open | Hybrowlabs Technologies Pvt Ltd |
| `UnityERP` | UnityERP | Open | EFFITRIX SYSTEMS PRIVATE LIMITED |
| `KRAYA` | KRAYA | Open | EFFITRIX SYSTEMS PRIVATE LIMITED |
| `IIM Bangalore` | IIMBX | Open | EFFITRIX SYSTEMS PRIVATE LIMITED |
| `Physics Wallah Gurukulam` | PWGK | Open | EFFITRIX SYSTEMS PRIVATE LIMITED |
| `Bhartiyam International School` | BTM SCL | Open | EFFITRIX SYSTEMS PRIVATE LIMITED |
| `MK Pawar Schools` | MK Pawar | Open | EFFITRIX SYSTEMS PRIVATE LIMITED |
| `Green Acres - Procure to Pay` | Green Acres - Procure to Pay | Open | EFFITRIX SYSTEMS PRIVATE LIMITED |
| `Bombay International School - Phase 1` | BIS - Phase 1 Implementation | Open | EFFITRIX SYSTEMS PRIVATE LIMITED |
| `Bombay International School - POC` | BIS - POC | Completed | EFFITRIX SYSTEMS PRIVATE LIMITED |
| `TGAA Phase 2` | TGAA P2 | Completed | EFFITRIX SYSTEMS PRIVATE LIMITED |

---

## Company nuance (Hybrowlabs) — read this

The Timesheet's own `company` field is normally the **employee's** company, not the project's.
For the Hybrowlabs profile the accepted company has been **`EFFITRIX SYSTEMS PRIVATE LIMITED`**; on
every site the company comes from the saved profile, never from this file.

But note the master above: the default project `PROJ-0019` (Walnut School) and `PROJ-0002`
(General Work) are registered under **Hybrowlabs Technologies Pvt Ltd**, while the client projects
are under EFFITRIX. This is a cross-company setup. If a timesheet is ever rejected for a
company/project mismatch, that's the cause — ask the user which company the timesheet should carry
rather than guessing. Do not silently switch the profile's company.

---

## Choosing a project

1. **If the user names a project or short code, use it** — match the Short Code column, then write
   the corresponding Project ID.
2. **Otherwise use the profile's default project.** Do not infer a project from repo names, environment
   URLs, or client names in the task text — that mapping is not defined here and guessing produces
   silently wrong timesheets.
3. **One project per row is allowed.** If a day genuinely spans different projects and the user has
   said so, set `project` per `time_logs` row instead of forcing one value.
4. **Flag Completed projects.** In the bundled snapshot `Bombay International School - POC` and
   `TGAA Phase 2` are Completed; a refreshed cache holds Open projects only, so a project missing from
   it may be Completed or hidden from this login. Generate the row but raise it in the ⚠️ section.
5. **Never invent a project ID.** If you can't resolve one, ask.
