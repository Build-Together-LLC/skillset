# Frappe / ERPNext Hot Paths Checklist

Use this when the target app is Frappe, ERPNext, HRMS, Frappe CRM, Helpdesk, custom Frappe apps, or Frappe Cloud.

## High-risk hot paths

### Login / boot / session

Symptoms:
- login API slow;
- Desk/webapp appears stuck after login;
- many workers time out after users start logging in;
- DB processlist has metadata/table states.

Check:
- `frappe.auth.LoginManager.post_login()` customizations;
- `boot.py`, session hooks, user/role permission loading;
- table count/cache rebuilds;
- `information_schema.tables` queries;
- MariaDB states: `Opening tables`, locks, temp/filesort;
- table cache settings: `table_open_cache`, `table_definition_cache`, `Opened_table_definitions`, cache misses/overflows.

Rule: login should not synchronously run expensive best-effort cache rebuilds.

### Document loading

Symptoms:
- API returns few rows but loads hundreds of docs;
- SQL count is very high;
- child tables queried repeatedly;
- custom hooks run once per doc.

Check:
- loops over `frappe.get_doc()`;
- loading full docs before filtering by status/user/company/direct reportee;
- `Document.onload` hooks;
- custom app monkey patches;
- child tables loaded for every doc;
- `doc.as_dict()` on large documents.

Rule: filter and paginate in SQL first, then enrich only final rows.

### Permissions / metadata

Symptoms:
- repeated Redis/cache gets;
- repeated pickle loads;
- repeated `Document.meta` calls;
- slow serialization of new/unnamed child docs.

Check:
- custom permission monkey patches;
- role/user permission logic inside list/report flows;
- cache key dimensions: doctype, docname, user, request context;
- request-local caching opportunities;
- invalidation path when permission rules change.

Rule: permission optimization must preserve effective access; compare old/new allowed fields/docs for representative users.

### Virtual/custom field-value layers

Symptoms:
- one extra query per loaded doc;
- tables like `Custom Doctype Field Values` queried repeatedly;
- app added virtual fields to bypass Frappe field-count limits.

Check:
- `on_load` hooks that hydrate virtual fields globally;
- whether list/report/inbox APIs actually need virtual fields;
- batch-load possibility;
- opt-in hydration flags;
- request-local cache.

Rule: virtual field hydration should not run automatically for every `get_doc()` unless the caller needs it.

### Approval / ToDo / inbox APIs

Symptoms:
- hundreds of ToDos/references loaded to return 1–10 rows;
- direct reportee/status filtering happens after full doc load.

Check:
- `ToDo` fetch logic;
- reference doctype/name filters;
- direct-reportee/employee/company filters;
- custom allocated user/role child tables;
- final pagination location.

Rule: prefilter reference documents and allocations, then load only page results.

## Useful commands

### Bench/app information

```bash
bench --site <site> list-apps
bench --site <site> doctor
bench --site <site> show-config
```

### MariaDB quick checks

```sql
SHOW FULL PROCESSLIST;
SHOW ENGINE INNODB STATUS\G
SHOW GLOBAL STATUS LIKE 'Opened_table_definitions';
SHOW GLOBAL STATUS LIKE 'Table_open_cache%';
SHOW VARIABLES LIKE 'table%cache%';
```

### Query profiling pattern in a bench console

```python
import time, frappe
start = time.perf_counter()
# call handler or function here
elapsed = time.perf_counter() - start
print('elapsed', elapsed)
```

If deeper SQL tracing is needed, monkey patch `frappe.db.sql` temporarily in a local probe and restore it after the run.

## Correctness checks after optimization

- Compare response shape before/after.
- Compare row counts and key fields.
- Compare permissions for admin and restricted users.
- Check cache invalidation when permission or virtual-field config changes.
- Verify no hidden mutating API was replayed during load tests.
