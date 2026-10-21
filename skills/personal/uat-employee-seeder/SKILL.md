---
name: uat-employee-seeder
description: Create sample/test Employee records on a Walnut UAT / non-production Frappe site with real-looking names and all required fields, bypassing the Google Workspace integration by temporarily toggling the Google Service Account `create_employee_workspace` flag off, creating the employees, then restoring it. Use when the user asks to "create sample employees", "seed test employees", "make dummy employees on UAT", "add employees bypassing google", or similar. HARD SAFETY RULE: this skill NEVER writes to production (erp.walnutedu.in) — it stops immediately if the target is prod.
---

# UAT Employee Seeder (Google-integration-safe)

Create N sample Employee records on a **UAT / non-production** Walnut Frappe site, with real-looking names and every mandatory field, while the Google Workspace user-creation step is bypassed. This automates the flow: **toggle Google off → create employees → toggle Google back on**.

## 🔴 NON-NEGOTIABLE SAFETY RULE — production is off-limits

**This skill must NEVER perform any write against production.**

- The production site is **`https://erp.walnutedu.in`**. If the target base URL contains `erp.walnutedu.in` (or any host you cannot positively confirm is a UAT/test site), **STOP immediately and do nothing** — no reads, no writes, no flag toggle. Tell the user you refuse because it is production.
- Only proceed when the host is a known UAT/test site, e.g. `unity-uat.m.frappe.cloud` or `uat.unityedu.tech`. If unsure, ask the user to confirm it is non-prod before doing anything.
- The bundled script (`scripts/seed_uat_employees.py`) enforces this with a denylist + allowlist and aborts on prod. Do not remove or weaken that guard.

## Why the toggle is needed

On these sites, `Employee.after_insert` runs the Google Workspace user step, gated by the **Single** doctype **Google Service Account**, field **`create_employee_workspace`**. When it is `1`, inserting an Employee throws `Branch is mandatory to create a google user account` (and, if branch/role were supplied, would attempt to create a **real** Google account). Providing branch/role does **not** bypass it — the only safe bypass is to set `create_employee_workspace = 0` for the duration, then restore it.

Also leave `company_email` and `user_id` **blank** — those are what the code derives the Google/Frappe user from. With them blank and the flag off, no Google account and no Frappe User are created.

## Required Employee fields (Walnut UAT)

Standard + site-mandatory (discovered on UAT; re-check if creation fails on a new mandatory field):

| Field | Notes |
|---|---|
| `first_name`, `last_name`, `employee_name` | real-looking name; `employee_name` = "First Last" |
| `gender` | must be an existing Gender (e.g. `Male` / `Female`) |
| `date_of_birth` | past date |
| `date_of_joining` | >= DOB |
| `company` | valid Company (e.g. `Unique Educational and Sports Foundation`) |
| `status` | `Active` |
| `cell_number` | 10-digit; unique per employee |
| `attendance_device_id` | unique string |
| `holiday_list` | valid Holiday List (e.g. `Walnut`) |
| `default_shift` | valid Shift Type (e.g. `Morning`) |
| `company_email`, `user_id` | **leave blank** (bypass) |

## Procedure

1. **Confirm the target is UAT/non-prod** (see safety rule). If it's `erp.walnutedu.in`, refuse.
2. Read and remember the current flag: `frappe.client.get_single_value(doctype="Google Service Account", field="create_employee_workspace")`.
3. (If any mandatory Link value is unknown) fetch a valid `Company`, `Holiday List`, `Shift Type`.
4. Set the flag off: `frappe.client.set_value(doctype="Google Service Account", name="Google Service Account", fieldname="create_employee_workspace", value=0)`.
5. Create each Employee: `POST /api/resource/Employee` with the fields above (no `company_email`/`user_id`).
6. **Always restore** the flag to its original value (step 2) — even if a creation fails. Use a finally/trap so a mid-run error never leaves Google disabled.
7. Verify: flag restored to original; list the created employees; confirm no `User` was created for them.
8. Remind the user to **rotate the API key** (it ends up in the transcript).

## Preferred: run the bundled script

`scripts/seed_uat_employees.py` does all of the above with the prod-guard, flag restore-on-exit, and verification. Run it with the UAT credentials:

```bash
python3 .claude/skills/uat-employee-seeder/scripts/seed_uat_employees.py \
  --base-url https://unity-uat.m.frappe.cloud \
  --key <API_KEY> --secret <API_SECRET> \
  --company "Unique Educational and Sports Foundation" \
  --holiday-list "Walnut" --default-shift "Morning" \
  --count 5
```

Optionally pass `--names "Rahul Sharma:Male:1995-01-10,Priya Deshmukh:Female:1994-03-22,..."` to control names/genders/DOBs; otherwise it uses a built-in real-name roster. It prints each created Employee id, restores the flag, and verifies no User leaked.

Prefer the user run it with their own credentials (keeps the secret out of the transcript). It refuses to run against `erp.walnutedu.in`.
