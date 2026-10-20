# Frappe API — what the timesheet commands call, and why

The profile's `site` is any Frappe / ERPNext **v15 or v16** site. Every call below is made by `scripts/ts_frappe.py` (`FrappeClient`); the commands
`sync`, `update`, `amend`, `cancel`, `submit` and `pull` (in `ts_lifecycle.py`) compose them. This file explains
what each call does, what Frappe does with it, and how failures are read.

## Authentication and transport

| Mode | Environment variables | How it's sent |
|---|---|---|
| API key (preferred) | `FRAPPE_API_KEY`, `FRAPPE_API_SECRET` | `Authorization: token <key>:<secret>` |
| Password | `FRAPPE_USER`, `FRAPPE_PASSWORD` | `POST /api/method/login` with `usr`/`pwd`, then the session cookie |

- Credentials are read from the environment for one run. Never saved, printed, put in an error, the audit log or any output.
  `FrappeError` messages carry only the sanitised server message (tags stripped; a message that contains a
  current secret is replaced by `[redacted]`), never request headers or bodies.
- The site must be `https://`; plain `http://` is accepted only for loopback (`localhost`, `127.0.0.1`, `::1`).
- **Redirects** (`ts_common.build_opener`): followed only when same origin (scheme, host, port with default ports
  normalised) **and** a GET. A cross-origin redirect, or any redirect of a POST/PUT/DELETE, raises
  `FrappeError(code="redirect")` before another request is made, so the `Authorization` header and session cookie
  never leave the configured site and a write is never replayed.
- **Proxies**: for a loopback site the opener ignores `http(s)_proxy` (`ProxyHandler({})`), so credentials and test
  traffic never go through a proxy. For other sites the standard proxy environment applies.
- `FrappeClient(site, ..., opener=...)` accepts an injected opener (tests, special transports).

## Calls

| Purpose | Call | Client method |
|---|---|---|
| Who am I | `GET /api/method/frappe.auth.get_logged_user` | `logged_user()` |
| My Employee | `GET /api/resource/Employee?filters=[["user_id","=",U]]` | `employees_for_user(U)` |
| Generic list (catalogue, overlap, amended_from…) | `GET /api/resource/<DocType>?filters&fields&limit_page_length=0` | `list_docs(doctype, filters, fields, order_by=None)` |
| The day's sheets | `GET /api/resource/Timesheet?filters=[employee, start_date<=D, end_date>=D]` | `timesheets_for(E, D)` |
| Read one sheet | `GET /api/resource/Timesheet/<name>` | `get_timesheet(name)` |
| **Workflow detection** | `GET /api/method/frappe.desk.form.load.getdoctype?doctype=Timesheet` → `docs[].__workflow_docs` | `workflow_for(doctype, doc=None)` |
| **Permission check** | `GET /api/method/frappe.client.has_permission?doctype&docname&perm_type` | `has_permission(doctype, name, ptype)` |
| Create draft | `POST /api/resource/Timesheet` | `create_timesheet(payload)` |
| Overwrite draft | `PUT /api/resource/Timesheet/<name>` (body includes `modified`) | `update_timesheet(name, payload, modified)` |
| **Submit** (no workflow) | `POST /api/method/frappe.client.submit` body `{"doc": "<full doc JSON>"}` | `submit_doc(doc)` |
| **Delete draft** | `DELETE /api/resource/Timesheet/<name>` (HTTP 202) | `delete_timesheet(name)` |
| Cancel submitted | `POST /api/method/frappe.client.cancel` `{doctype, name}` | `cancel_timesheet(name)` |
| Workflow actions | `POST /api/method/frappe.model.workflow.get_transitions` / `.apply_workflow` | `workflow_transitions(doc)` / `apply_workflow(doc, action)` |

### `workflow_for(doctype, doc=None)` → `None | {name, document_type, workflow_state_field, states[]}`

`states[]` is `{state, doc_status, allow_edit}`; `doc_status` is the string `"0"`, `"1"` or `"2"` (it is a Select field in
Frappe; compare with `str()`).

- **Never detect a workflow by listing the `Workflow` doctype.** It is readable by System Manager only, so for an
  Employee / Projects User / HR User the list is a 403 — which must neither crash every submit nor be read as "no
  workflow". `getdoctype` builds the form meta (`FormMeta.load_workflows`) and returns the active Workflow and its
  states regardless of Workflow permissions.
- **Fails closed**: any HTTP/network error, a malformed answer, or a doc that carries a `workflow_state` while
  detection returns none raises `FrappeError` (`code` = classified, or `workflow_unknown`). `None` is returned only when
  the server answered and listed no workflow. Callers must stop on the error and never fall through to plain submit.
- Why it matters: a **plain `frappe.client.submit` on a workflow doctype bypasses approval.** `validate_workflow` only checks a
  transition when `workflow_state` changed between the DB and the document; a client doc carries the same state, so
  nothing is checked and `set_workflow_state_on_action` just moves to the first `doc_status 1` state. Only the client-side
  guard (detect, then use `apply_workflow`) prevents this.

### `update_timesheet(name, payload, modified)` and `modified` semantics

- Pass the `modified` string from the GET **verbatim** (`"2026-09-08 18:02:11.123456"`). Frappe's `update_doc` copies the
  body into the loaded doc, so `check_if_latest` compares the client value with the DB: a mismatch raises
  `TimestampMismatchError` (HTTP 417, `code="conflict"`) and nothing is written.
- If `modified` is omitted Frappe compares the DB value with itself — **no check, last write wins**. The client therefore
  refuses an empty `modified`.
- `frappe.client.submit` behaves the same (it builds the doc from the JSON and calls `submit()` → `save()`), and must be sent
  the **full** doc as read: a skeleton `{doctype, name, modified}` would make `save` delete the child rows.
- `get_transitions` and `apply_workflow` do `get_doc(...).load_from_db()`: the client's `modified` is discarded and there is
  **no server-side race check**. `frappe.client.cancel` takes no `modified` either. For these, re-GET immediately before and
  compare `modified` with the plan-time value (a narrow window remains; it is documented, not closed).
- A draft `PUT` replaces every row: sending `time_logs` clears the child rows and re-adds what was sent.

## Frappe v15 behaviour the commands rely on

- **Submitted sheets can't be edited** (`time_logs` is not `allow_on_submit`): `UpdateAfterSubmitError`. Cancel → amend is the route.
- **Amended names.** With the default "Amend Counter", amending `TS-2026-14700` creates `TS-2026-14700-1`, amending that
  creates `-2`. With "Default Naming" (Document Naming Settings, or a per-doctype override) it gets a fresh series number.
  Never assume `-1`. `amended_from` requires the source to be cancelled (`docstatus 2`).
- **The server recomputes** on save (`Timesheet.validate`): row hours/`to_time`, `start_date`/`end_date`/`total_hours`, and the
  **costing** fields (`costing_rate`, `costing_amount`, billing amounts from Activity Cost) when we send zeros. A built doc therefore
  never equals the stored one; diffs compare an explicit field set only (header: `company, employee, note, start_date,
  end_date, total_hours`; rows by idx: `activity_type, from_time, to_time, hours, project, description`). The `note` field is a
  Text Editor (HTML on read), and description text containing `<`/`>` is rewritten by `_sanitize_content`.
- **Overlaps.** Rows overlapping another *active* sheet of the same employee are rejected unless Projects Settings ignores
  employee time overlap. A cancelled sheet doesn't count. The server check is authoritative; a client-side preflight is best effort.
- **Delete.** `DELETE /api/resource/Timesheet/<name>` needs the `delete` permission, answers 202, `404 DoesNotExistError` when
  missing and `417 LinkExistsError` when linked. Submitted docs are refused. The JSON is kept in "Deleted Document" (a privileged
  user can restore it); this tool never restores it.
- **Direct cancel vs workflow.** `cancel_timesheet` tries `frappe.client.cancel` first, which — like plain submit — does not run
  workflow transitions; only if refused does the code look for a workflow action leading to a `doc_status "2"` state. Kept as
  is (pinned by an existing test).
- **Workflow actions.** `get_transitions` returns the actions *this user's roles* may take (`action`, `next_state`,
  `allow_self_approval`, `condition`); it raises `WorkflowStateError` when the state field is empty. The usual employee
  action is "Send for Approval" (next state `doc_status 0`) after which an approver submits. `apply_workflow` raising "Self approval
  is not allowed" is a plain `ValidationError` (417), and `allow_self_approval` defaults to on.
- **Errors carry `exc_type`** only on the `/api` v1 endpoints (`frappe.utils.response.report_error`).

## Permission matrix (Timesheet doctype, stock ERPNext)

| Role | read | write/create | submit | cancel | delete | amend |
|---|---|---|---|---|---|---|
| Employee | yes (own) | yes | no | no | no | no |
| Projects User, HR User, Manufacturing User, Accounts User | yes | yes | yes | yes | yes | yes |
| System Manager / Administrator | all | all | all | all | all | all |

Site customisation changes this, so the commands ask the server: `has_permission(doctype, name, "submit"|"cancel"|"delete"|"write")`
is called during the **dry run**, so a user who cannot cancel hears so before being asked to approve, not after.

## Error table (`FrappeError.code`)

`FrappeError` has `status` (HTTP, `None` if unreachable), `exc_type` (raw Frappe value) and `code` (normalised). Matching order:
specific `exc_type` → specific message substring → generic `ValidationError`/`MandatoryError` → HTTP status. Substrings are
English-only (Frappe translates per user language); anything unmatched is `error` carrying the sanitised server message.

| Trigger | `code` | Meaning / next step |
|---|---|---|
| `TimestampMismatchError`, "Document has been modified after you have opened it" | `conflict` | Changed since it was read. Nothing written. `pull` again. |
| `LinkExistsError`, "is linked with", "Cannot delete or cancel because" | `linked_docs` | A Salary Slip / invoice etc. links it. Handle that first. Nothing changed. |
| `WorkflowPermissionError`, `WorkflowTransitionError`, "Self approval is not allowed", "Not a valid Workflow Action" | `workflow_blocked` | The workflow forbids this user's action. The approver acts. |
| `UpdateAfterSubmitError`, "Not allowed to change … after submission" | `immutable_submitted` | Use amend. |
| `DocstatusTransitionError`, "Cannot edit cancelled document" | `state_changed` | Someone changed the state. Re-read and re-plan. |
| "is overlapping with TS-…" | `overlap` | Another active sheet covers those hours. |
| 417 "attendance is not marked Present" (Frappe also prints `Field weekly_off_based_on does not exist on HR Settings`) | `attendance` | HRMS refuses a Timesheet for a day with no Present attendance, typically a Sunday or holiday. The HR Settings text is a side effect. Retrying cannot help; get attendance marked or move the hours to another day. |
| `ValidationError`, `MandatoryError`, "Could not find …", "Value missing for" | `validation` | Fix the spec (activity type, project, mandatory field) and rebuild. |
| 403, `PermissionError`, "Not permitted" | `permission` | The role can't do it. Nothing to retry. |
| 401, "Invalid login" | `auth` | Recheck or regenerate credentials. |
| 404, `DoesNotExistError` | `not_found` | Wrong name or already deleted (a successful delete verify). |
| other 5xx | `server` | Safe to re-run; every command re-reads state first. |
| network failure | `unreachable` | Site down or wrong URL. |
| cross-origin / write redirect | `redirect` | Wrong site URL; credentials were not sent. |
| workflow state present but not detected | `workflow_unknown` | Refused; ask the user. |

Messages are the sanitised server text; the exact string `Frappe <METHOD> <path> failed (<status>): <detail>` is stable.

## Operations in order (what the commands do)

1. Identify: `logged_user` → `employees_for_user`; the timesheet's `employee` must be among them (else stop before any write).
2. Read the sheet fresh (`get_timesheet`) and remember `modified`; probe `workflow_for` and `has_permission` for the planned write.
3. Dry run prints the plan, the diff and `modified`. Writes happen only with the plan-matching confirm flag and the matching
   `--expect-modified`.
4. Write (`create`/`update`/`submit`/`delete`/`cancel`/workflow). Re-read and verify the post-condition (docstatus, state).
5. Nothing submits as a side effect of save/update/amend; submit is its own command with its own confirmation.

## Replaced / removed

- `workflow_cancel_states()` → `workflow_for(...)["states"]` filtered by `str(doc_status) == "2"` (no System Manager read needed).
- `update_timesheet(name, payload)` → `update_timesheet(name, payload, modified)`.
- `sync --apply` / `--confirm-cancel` → per-action flags (`--confirm-create|update|cancel|delete|submit`) plus `--expect-modified`.
