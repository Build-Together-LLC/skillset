# DocType JSON — Schema Review Rules

Review DocType JSON files (found at `{app}/{module}/doctype/{doctype}/{doctype}.json`) for
structural correctness, naming conventions, permission hygiene, and schema design.

---

## Field Design

### 🟠 Major
- **Data fields used for predefined options** — if a field only accepts a fixed set of values,
  it should be a `Select` or `Link` field, not `Data`. Data fields invite inconsistency.
- **Missing mandatory flag** on fields that should always be filled (e.g., `student_name` on a
  Student DocType). Check if `validate()` enforces it in code — if not, the JSON should.
- **Overuse of `Small Text` or `Text` for short values** — use `Data` for single-line strings
  (<140 chars), `Small Text` for multi-line (<500 chars), `Text` for longer content.
- **Currency/Float fields without precision** — missing `precision` leads to rounding issues.
- **Link fields pointing to non-existent DocTypes** — cross-reference if possible. At minimum,
  flag if the linked DocType name looks suspicious or doesn't follow naming conventions.
- **Missing `in_list_view` on important fields** — if a child table has 10 fields but none are
  marked `in_list_view`, the list view will be useless.

### 🟡 Minor
- **Field labels not sentence case** — Frappe convention is "Student Name", not "student_name"
  or "STUDENT NAME" in the label.
- **Fieldname not snake_case** — all fieldnames should be lowercase snake_case.
- **Section Break / Column Break without label** when a label would aid readability.
- **`hidden` fields that are also `mandatory`** — contradictory unless set via code.
- **Overly long fieldnames** (>40 chars) — keep concise.
- **Missing `description` on fields** where the label alone is ambiguous.

### 💡 Suggestions
- Consider using `Tab Break` to organize forms with many fields (v15 feature).
- Fields that are always computed should have `read_only: 1` to prevent manual editing.
- `Attach` fields should specify `options` for allowed file types if applicable.

---

## Naming & Autoname

### 🟠 Major
- **Missing `autoname` pattern** — DocType will use random hash naming, which is rarely desired
  for master data. Should typically be `naming_series`, `field:{fieldname}`, `format_string`,
  or `Prompt`.
- **`autoname: Prompt`** on a transactional DocType — user shouldn't manually name transactions.
- **`autoname: field:` pointing to a non-unique field** — will cause duplicate name errors.

### 🟡 Minor
- Naming series pattern not following conventions (e.g., `STU-.YYYY.-` for Student).
- Naming series prefix too generic (e.g., `REC-` which could conflict across modules).

---

## Permissions

### 🔴 Critical
- **No permissions defined at all** — DocType is accessible to no one (or everyone via admin).
  Every DocType should have explicit role permissions.
- **`allow_guest_access: 1`** without strong justification — public access to a DocType.
- **Write/Delete permissions granted to roles that should be read-only** for this DocType.

### 🟠 Major
- **Overly permissive roles** — e.g., "All" role having write access to sensitive DocTypes.
- **Missing role for a workflow actor** — if there's a workflow, ensure the approver role has
  proper permissions.
- **`user_permission_doctypes`** misconfigured, breaking multi-tenant data isolation.

### 🟡 Minor
- Permissions not including `report` or `export` for roles that likely need them.
- Inconsistent permission levels across related DocTypes.

---

## Workflow & Submission

### 🟠 Major
- **`is_submittable: 1` without `on_submit` / `on_cancel` handlers** — submittable DocTypes
  usually need side effects (ledger entries, notifications). If neither exists, question why
  it's submittable.
- **Workflow states referencing roles that don't exist** in the permission model.
- **Missing `default` workflow state** for new documents.

### 🟡 Minor
- `is_submittable` used for DocTypes that don't represent transactions (overengineering).
- Workflow with too many states (>7) — consider simplifying.

---

## Child Tables

### 🟠 Major
- **Child DocType without `istable: 1`** — will appear in the sidebar as a standalone DocType.
- **Child table fields missing `in_list_view: 1`** — at least 2-3 fields should be visible.
- **Child table without `reqd` fields** — if every row needs certain fields, mark them mandatory.
- **Parent DocType not listing the child table field** — orphaned child table definition.

### 🟡 Minor
- Child table with too many fields (>15) — consider whether some belong on the parent.
- Missing `idx` handling notes if row order matters.

---

## Schema Changes in PRs

When a PR modifies a DocType JSON, pay special attention to:

### 🔴 Critical
- **Removing a field that might contain production data** without a migration/patch.
- **Changing field type** (e.g., `Data` → `Int`) without a data migration patch.
- **Renaming a fieldname** — this doesn't auto-migrate; needs a patch.

### 🟠 Major
- **Adding a `mandatory` field** without a default value or patch to backfill existing records.
- **Changing `autoname` pattern** on a DocType with existing data.
- **Modifying permissions** that could lock out existing users.
- **No corresponding patch file** when schema changes require data migration.
  Check if `patches.txt` has a new entry.

### 🟡 Minor
- Field order changes that might confuse users familiar with the current layout.
- Adding fields without updating print formats that display the DocType.

---

## JSON Hygiene

### 🟡 Minor
- **`modified` and `modified_by` changes** in the JSON diff — these are auto-generated and
  create noisy diffs. Ideally stripped before commit. Flag as noise but don't block.
- **`creation` timestamp changes** on existing DocTypes — suspicious, likely an accidental
  re-export.
- **Inconsistent `sort_field` / `sort_order`** — should match how users expect to see records.
- **`track_changes: 0`** on DocTypes where audit trail matters.
- **`allow_rename: 0`** on master data where admins might need to rename.
