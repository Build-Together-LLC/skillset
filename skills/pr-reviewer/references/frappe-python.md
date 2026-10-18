# Frappe/ERPNext v15 — Python Backend Review Rules

## Table of Contents
1. [ORM & Database](#orm--database)
2. [API Design](#api-design)
3. [Controller Patterns](#controller-patterns)
4. [Hooks & App Structure](#hooks--app-structure)
5. [Performance](#performance)
6. [Frappe v15 Specifics](#frappe-v15-specifics)
7. [Jinja Templates](#jinja-templates)
8. [Background Jobs & Scheduling](#background-jobs--scheduling)
9. [Translations](#translations)
10. [Testing Patterns](#testing-patterns)

---

## ORM & Database

### 🔴 Critical — SQL Injection
```python
# BAD — string interpolation in SQL
frappe.db.sql(f"SELECT * FROM `tabStudent` WHERE name = '{student_id}'")
frappe.db.sql("SELECT * FROM `tabStudent` WHERE name = '%s'" % student_id)

# GOOD — parameterized query
frappe.db.sql("SELECT * FROM `tabStudent` WHERE name = %s", (student_id,))
frappe.db.sql("SELECT * FROM `tabStudent` WHERE name = %(student)s", {"student": student_id})

# BETTER — use the ORM
frappe.get_all("Student", filters={"name": student_id})
```
Flag ANY string interpolation/concatenation inside `frappe.db.sql()` as 🔴 Critical.

### 🟠 Major — ORM Misuse
- Using `frappe.get_doc()` when only one field is needed → use `frappe.db.get_value()`
- Using `frappe.db.sql()` when `frappe.get_all()` / `frappe.get_list()` would work
- Missing `as_dict=True` on `frappe.db.sql()` leading to fragile tuple indexing
- Calling `doc.save()` inside a loop without `frappe.db.commit()` strategy
- Using `frappe.db.set_value()` in a loop instead of bulk update

### 🟡 Minor — Query Style
- `frappe.get_all()` without explicit `fields` parameter (fetching all fields unnecessarily)
- Not using `pluck` when only one field is needed: `frappe.get_all("X", pluck="name")`
- Using `limit_page_length=0` without a comment explaining why all records are needed
- Raw SQL when ORM equivalent exists and is cleaner

---

## API Design

### 🔴 Critical — Permission Bypass
```python
# BAD — no permission check on whitelisted method
@frappe.whitelist()
def delete_student(student_id):
    frappe.delete_doc("Student", student_id)

# GOOD — explicit permission check
@frappe.whitelist()
def delete_student(student_id):
    frappe.has_permission("Student", "delete", throw=True)
    frappe.delete_doc("Student", student_id)
```
Every `@frappe.whitelist()` method that modifies data MUST have permission checks
unless `allow_guest=True` is intentional and justified.

### 🟠 Major — API Issues
- `@frappe.whitelist(allow_guest=True)` without clear justification — flag and ask why
- Whitelisted method that does too many things (>30 lines) — should be broken up
- Returning raw `frappe.db.sql()` results instead of sanitized dicts
- Missing input validation on whitelisted method parameters
- Not using `frappe.form_dict` properly for form submissions
- Method modifies data but doesn't return meaningful confirmation

### 🟡 Minor — API Style
- Missing docstring on whitelisted method
- Method name doesn't clearly describe the action
- Inconsistent return format across related methods

### Flags & Permissions
```python
# BAD — blanket permission bypass
frappe.flags.ignore_permissions = True
doc.save()

# ACCEPTABLE — with clear scope
frappe.flags.ignore_permissions = True
try:
    doc.save()
finally:
    frappe.flags.ignore_permissions = False

# BETTER — use run_doc_method or set on specific doc
doc.flags.ignore_permissions = True
doc.save()
```
Flag any `frappe.flags.ignore_permissions = True` without a corresponding reset as 🟠 Major.

---

## Controller Patterns

### Where Logic Belongs
- **`validate()`** — input validation, cross-field checks, permission-based field restrictions
- **`before_save()`** — computed fields, derived values, auto-population
- **`on_submit()`** — side effects (ledger entries, notifications, linked doc creation)
- **`on_cancel()`** — reverse side effects cleanly
- **`before_insert()`** — one-time setup, auto-naming

Flag these as 🟠 Major:
- Business logic in `__init__` instead of lifecycle hooks
- Side effects (emails, API calls, doc creation) in `validate()` — these belong in `on_submit`/`after_insert`
- Heavy computations in `validate()` that should be in `before_save()`
- Missing `on_cancel()` when `on_submit()` creates linked documents

### 🟡 Minor — Controller Style
- Controller class with methods unrelated to the DocType lifecycle
- Super-long `validate()` that should be split into private methods
- Missing `super().validate()` call when overriding (unless intentional)

---

## Hooks & App Structure

### hooks.py
- `doc_events` handlers pointing to methods that don't exist → 🔴 Critical
- `doc_events` with `*` wildcard without justification → 🟠 Major
- Fixtures listing DocTypes that shouldn't be fixtures (transactional data) → 🟠 Major
- `scheduler_events` pointing to heavy functions without `frappe.enqueue` → 🟠 Major
- Missing entries in `hooks.py` when new controllers have lifecycle methods → 🟡 Minor

### App Structure
- Python files outside the module folder structure → 🟡 Minor
- Utils file growing beyond 500 lines → 🟡 Minor (suggest splitting)
- Circular imports between modules → 🟠 Major
- `__init__.py` files with actual logic → 🟡 Minor

---

## Performance

### 🟠 Major — N+1 and Loop Queries
```python
# BAD — N+1 query pattern
students = frappe.get_all("Student", fields=["name"])
for s in students:
    enrollment = frappe.get_doc("Student Enrollment", {"student": s.name})  # DB hit per student!
    # ...

# GOOD — batch fetch
students = frappe.get_all("Student", fields=["name"])
student_names = [s.name for s in students]
enrollments = frappe.get_all("Student Enrollment",
    filters={"student": ["in", student_names]},
    fields=["name", "student", "program"])
enrollment_map = {e.student: e for e in enrollments}
```
Flag any `frappe.get_doc`, `frappe.get_all`, or `frappe.db.sql` inside a for/while loop as 🟠 Major.

### 🟠 Major — Other Performance Issues
- `frappe.get_doc()` when `frappe.db.get_value()` suffices (loads full doc + children)
- Missing `limit_page_length` on `get_all` that could return thousands of records
- Synchronous heavy operations (PDF generation, bulk email) not using `frappe.enqueue`
- `frappe.db.count()` with complex filters instead of a targeted SQL count
- Large file processing in request thread instead of background job

---

## Frappe v15 Specifics

Flag these deprecated/outdated patterns:
- Using `frappe.get_list` with `ignore_permissions=True` instead of proper role permissions → 🟠
- Old-style `frappe.client.get_list` patterns → 🟡
- Using `frappe.get_doc` for read-only access (use `frappe.get_cached_doc` or `get_all`) → 🟡
- Not using type hints on whitelisted method parameters (v15 encourages this) → 💡
- Using `frappe.msgprint` for errors instead of `frappe.throw` → 🟡
- Using `frappe.local.response` directly instead of returning from whitelisted methods → 🟡

---

## Jinja Templates

### 🔴 Critical — XSS in Templates
```html
<!-- BAD — unescaped user input -->
{{ doc.custom_html_field }}
{{ frappe.db.get_value("Settings", None, "header_html") }}

<!-- GOOD — escaped or explicitly marked safe after sanitization -->
{{ doc.student_name | e }}
{{ doc.custom_html_field | sanitize_html }}
```
Flag any `{{ variable }}` rendering user-controlled HTML content without `| e` or `| sanitize_html`.

### 🟡 Minor — Template Style
- Complex Python logic in Jinja templates (move to controller/context)
- Hardcoded styles in templates instead of CSS classes
- Missing `{% if %}` null checks on optional fields

---

## Background Jobs & Scheduling

- `frappe.enqueue` without `queue` parameter (defaults to "default" which may be overloaded) → 🟡
- Missing `timeout` on long-running enqueued jobs → 🟡
- Scheduled job that could take >15 minutes without chunking logic → 🟠
- `frappe.enqueue` with `now=True` in production code (defeats the purpose) → 🟠
- Missing idempotency — job that breaks if run twice → 🟠

---

## Translations

- User-facing strings not wrapped in `frappe._()` or `_()` → 🟡 Minor
- f-strings inside `_()` (breaks translation extraction):
  ```python
  # BAD
  frappe.throw(_(f"Student {name} not found"))
  # GOOD
  frappe.throw(_("Student {0} not found").format(name))
  ```
  Flag as 🟠 Major since it silently breaks translations.

---

## Testing Patterns

When reviewing test files (`test_*.py`):
- Tests that depend on specific data existing in the DB without setup → 🟠
- Tests without teardown/cleanup → 🟡
- Tests that test implementation details rather than behavior → 💡
- Missing edge case tests for validation logic → 💡
- Test methods without descriptive names → 🟡
