"""Shared in-memory fake of FrappeClient for tests. Not a test module."""
from __future__ import annotations

import copy
import datetime as dt
import re

from ts_frappe import FrappeError

READS = (
	"list_docs",
	"get",
	"logged_user",
	"employees_for_user",
	"timesheets_for",
	"workflow_for",
	"has_permission",
	"workflow_transitions",
)


def _like(value, pattern) -> bool:
	regex = "".join(".*" if char == "%" else "." if char == "_" else re.escape(char) for char in str(pattern))
	return re.fullmatch(regex, str(value), re.I | re.S) is not None


OPERATORS = {
	"=": lambda value, other: value == other,
	"!=": lambda value, other: value != other,
	"<": lambda value, other: value < other,
	"<=": lambda value, other: value <= other,
	">": lambda value, other: value > other,
	">=": lambda value, other: value >= other,
	"in": lambda value, other: value in other,
	"like": _like,
}


def matches(row: dict, field: str, op: str, value) -> bool:
	"""Evaluate one `[field, op, value]` filter triple against a record; a missing field never matches ordered ops."""
	if op not in OPERATORS:
		raise ValueError(f"unsupported filter operator {op!r}")
	current = row.get(field)
	if current is None and op not in ("=", "!=", "in"):
		return False
	try:
		return bool(OPERATORS[op](current, value))
	except TypeError:
		return False


def _error(message: str, exc_type: str, status: int) -> FrappeError:
	return FrappeError(message, exc_type=exc_type, status=status)


class FakeClient:
	"""In-memory stand-in for `ts_frappe.FrappeClient`. FROZEN API (DevLifecycle codes against this).

	Constructor: `FakeClient(existing=(), employees=None, cancel_error=None, transitions=(), cancel_states=(),
	records=None, workflow=None, deny=(), linked=None, docs=None, user="employee@example.com")`
	- `existing`: Timesheet stubs (`name`, `docstatus`, optional `modified`/`employee`/dates); `docs`: full docs by name.
	- `records`: `{doctype: [row]}` served by `list_docs` for every doctype EXCEPT Timesheet, which is unified with the
	  live Timesheet store (so `amended_from`, `docstatus`, `employee` filters see writes made through the client).
	- `workflow`: None (no workflow) or `{"name", "states": [{"state", "doc_status": "0"|"1"|"2", "allow_edit"}]}`
	  (`cancel_states` is the legacy shortcut for states with doc_status "2").
	- `transitions`: list of `{"action", "next_state"}` or `{workflow_state: [...]}` returned by `workflow_transitions`.
	- `deny`: ptypes ("submit", "cancel", "delete", "write") the user lacks: `has_permission` is False and the write raises
	  a 403 `permission` error. `linked`: `{timesheet: "Salary Slip SAL-9"}`; cancel/delete raise `linked_docs`.
	- `cancel_error`: direct `cancel_timesheet` raises a 403 FrappeError with this message (legacy).

	Methods mirror FrappeClient (`logged_user employees_for_user timesheets_for get_timesheet list_docs workflow_for
	has_permission workflow_transitions create_timesheet update_timesheet(name, payload, modified=None) submit_doc
	delete_timesheet cancel_timesheet apply_workflow`) plus test helpers:
	`inject(op, exc, times=1)` (op: any client method name or recorded op: create update cancel submit delete workflow get
	list_docs logged_user ...; raises `exc` that many times, AFTER the call is recorded), `bump_modified(name) -> str`
	(a concurrent editor touched the doc), `writes()` (op names of non-read calls, attempts included), `reads()`,
	`calls` (tuples: ("create", payload) ("update", name, payload) ("cancel", name) ("workflow", name, action)
	("submit", doc) ("delete", name); reads: ("get", name) ("list_docs", doctype, filters, fields, order_by)
	("workflow_for", doctype) ("has_permission", doctype, name, ptype) ("logged_user",) ...).
	Reads are recorded too: assert `writes() == []`, not `calls == []`.

	It models Frappe v15: every write bumps `modified` (`YYYY-MM-DD HH:MM:SS.ffffff`); `update_timesheet`/`submit_doc` with a
	`modified` that differs from the stored one raise `conflict` and write nothing (`modified=None` is not checked, as in
	Frappe); update of docstatus != 0 raises `immutable_submitted`; `submit_doc` replaces child rows with the doc's (a doc
	without `time_logs` deletes them) and, like real Frappe, is NOT blocked by a workflow (the call is recorded so tests
	can assert it never happens); writes fill `costing_rate/costing_amount/billing_*` and `total_*` fields and add server
	noise (`owner`, `creation`, row `name`/`idx`), so a naive "built doc == remote doc" diff fails; `create_timesheet` with
	`amended_from` requires a cancelled source and names `<source>-1` (`-2`.. when amending an amendment or taken), fresh
	docs are `TS-NEW`, `TS-NEW-2`..; overlapping rows of the same employee on another active doc raise `overlap`.
	`apply_workflow` does NOT check `modified` (Frappe reloads the doc).
	"""

	CLOCK_START = dt.datetime(2026, 10, 1, 0, 0, 0)
	COSTING_RATE = 50.0
	BILLING_RATE = 100.0

	def __init__(
		self,
		existing=(),
		employees=None,
		cancel_error=None,
		transitions=(),
		cancel_states=(),
		records=None,
		workflow=None,
		deny=(),
		linked=None,
		docs=None,
		user="employee@example.com",
	):
		self.user = user
		self.employees = (
			[{"name": "HR-EMP-00001", "employee_name": "Example Employee"}] if employees is None else employees
		)
		self.cancel_error = cancel_error
		self.transitions = copy.deepcopy(transitions) if isinstance(transitions, dict) else list(transitions)
		if workflow is None and cancel_states:
			workflow = {"name": "Fake Workflow", "states": [{"state": state, "doc_status": "2"} for state in cancel_states]}
		self.workflow = copy.deepcopy(workflow)
		self.deny = set(deny)
		self.linked = dict(linked or {})
		self.records = {doctype: [dict(row) for row in rows] for doctype, rows in (records or {}).items()}
		self.calls = []
		self._injected: dict[str, list] = {}
		self._ticks = 0
		self._fresh = 0
		self.docs = {}
		for sheet in existing:
			self._store(dict(sheet))
		for name, doc in (docs or {}).items():
			self._store(dict(copy.deepcopy(doc), name=name))
		self.existing = [self.docs[sheet["name"]] for sheet in existing]

	# Plumbing

	def _store(self, doc: dict) -> dict:
		doc.setdefault("docstatus", 0)
		doc.setdefault("time_logs", [])
		doc.setdefault("modified", self._tick())
		self.docs[doc["name"]] = doc
		return doc

	def _tick(self) -> str:
		self._ticks += 1
		return (self.CLOCK_START + dt.timedelta(seconds=self._ticks)).strftime("%Y-%m-%d %H:%M:%S.%f")

	def inject(self, op: str, exc: Exception, times: int = 1) -> None:
		self._injected.setdefault(op, []).extend([exc] * times)

	def _enter(self, op: str, *record) -> None:
		self.calls.append((op, *record))
		queue = self._injected.get(op)
		if queue:
			raise queue.pop(0)

	def _require(self, name: str) -> dict:
		if name not in self.docs:
			raise _error(f"Timesheet {name} not found", "DoesNotExistError", 404)
		return self.docs[name]

	def _guard(self, name: str, ptype: str) -> dict:
		if ptype in self.deny:
			raise _error("Not permitted", "PermissionError", 403)
		doc = self._require(name)
		if ptype in ("cancel", "delete") and name in self.linked:
			raise _error(
				f"Cannot delete or cancel because Timesheet {name} is linked with {self.linked[name]}",
				"LinkExistsError",
				417,
			)
		return doc

	def _bump(self, doc: dict) -> None:
		doc["modified"] = self._tick()

	def _fill(self, doc: dict) -> None:
		"""What Timesheet.validate does on the server: costing/billing amounts, totals, noise fields."""
		doc.setdefault("owner", self.user)
		doc.setdefault("creation", "2026-09-08 09:00:00.000000")
		doc.setdefault("doctype", "Timesheet")
		total = 0.0
		for index, row in enumerate(doc.get("time_logs") or [], start=1):
			hours = float(row.get("hours") or 0)
			total += hours
			row["costing_rate"] = row.get("costing_rate") or self.COSTING_RATE
			row["costing_amount"] = round(row["costing_rate"] * hours, 2)
			row["billing_rate"] = row.get("billing_rate") or self.BILLING_RATE
			row["billing_amount"] = round(row["billing_rate"] * hours, 2) if row.get("is_billable") else 0.0
			row.setdefault("name", f"{doc['name']}-row{index}")
			row["idx"] = index
			row.setdefault("parent", doc["name"])
		if doc.get("time_logs"):
			doc["total_hours"] = round(total, 2)
			doc["total_costing_amount"] = round(sum(r["costing_amount"] for r in doc["time_logs"]), 2)
			doc["total_billable_amount"] = round(sum(r["billing_amount"] for r in doc["time_logs"]), 2)

	def _workflow_state_for(self, docstatus: int) -> str | None:
		for state in (self.workflow or {}).get("states", []):
			if str(state.get("doc_status")) == str(docstatus):
				return state["state"]
		return None

	def _check_overlap(self, doc: dict, ignore: str | None = None) -> None:
		for other in self.docs.values():
			if other["name"] in (ignore, doc.get("name")) or int(other.get("docstatus") or 0) == 2:
				continue
			if other.get("employee") != doc.get("employee"):
				continue
			for mine in doc.get("time_logs") or []:
				for theirs in other.get("time_logs") or []:
					if not (mine.get("from_time") and mine.get("to_time") and theirs.get("from_time") and theirs.get("to_time")):
						continue
					if mine["from_time"] < theirs["to_time"] and theirs["from_time"] < mine["to_time"]:
						raise _error(f"Row {mine.get('idx', 1)}: From Time is overlapping with {other['name']}", "OverlapError", 417)

	def _check_modified(self, doc: dict, modified) -> None:
		if modified is not None and modified != doc.get("modified"):
			raise _error("Document has been modified after you have opened it", "TimestampMismatchError", 417)

	# Reads

	def logged_user(self):
		self._enter("logged_user")
		return self.user

	def employees_for_user(self, user):
		self._enter("employees_for_user", user)
		return copy.deepcopy(self.employees)

	def timesheets_for(self, employee, date):
		self._enter("timesheets_for", employee, date)
		fields = ("name", "docstatus", "status", "start_date", "end_date", "total_hours", "modified")
		rows = []
		for doc in self.docs.values():
			if doc.get("employee") not in (None, employee):
				continue
			if doc.get("start_date") and doc["start_date"] > date or doc.get("end_date") and doc["end_date"] < date:
				continue
			rows.append({field: doc[field] for field in fields if field in doc})
		return sorted(rows, key=lambda row: row.get("modified") or "", reverse=True)

	def get_timesheet(self, name):
		self._enter("get", name)
		return copy.deepcopy(self._require(name))

	def list_docs(self, doctype, filters, fields, order_by=None):
		"""Generic query; Timesheet reads the live store, other doctypes read `self.records`."""
		self._enter("list_docs", doctype, filters, fields, order_by)
		source = self.docs.values() if doctype == "Timesheet" else self.records.get(doctype, [])
		rows = [row for row in source if all(matches(row, *flt) for flt in filters or [])]
		if order_by:
			field, _, direction = order_by.partition(" ")
			rows.sort(key=lambda row: (row.get(field) is None, row.get(field)), reverse=direction.strip().lower() == "desc")
		return [{field: copy.deepcopy(row[field]) for field in fields if field in row} for row in rows]

	def workflow_for(self, doctype, doc=None):
		self._enter("workflow_for", doctype)
		if self.workflow is None:
			if doc and doc.get("workflow_state"):
				raise FrappeError("workflow state present but no workflow detected", code="workflow_unknown")
			return None
		return {
			"document_type": doctype,
			"workflow_state_field": "workflow_state",
			**copy.deepcopy(self.workflow),
		}

	def has_permission(self, doctype, name, ptype):
		self._enter("has_permission", doctype, name, ptype)
		self._require(name)
		return ptype not in self.deny

	def workflow_transitions(self, doc):
		self._enter("workflow_transitions", doc.get("name"))
		if isinstance(self.transitions, dict):
			return copy.deepcopy(self.transitions.get(self.docs[doc["name"]].get("workflow_state"), []))
		return copy.deepcopy(self.transitions)

	# Writes

	def create_timesheet(self, payload):
		self._enter("create", copy.deepcopy(payload))
		doc = copy.deepcopy(payload)
		source = doc.get("amended_from")
		if source:
			if int(self._require(source).get("docstatus") or 0) != 2:
				raise _error(f"Cannot amend {source}: it is not cancelled", "ValidationError", 417)
			stem = source.rsplit("-", 1)[0] if self.docs[source].get("amended_from") else source
			counter = int(source.rsplit("-", 1)[1]) + 1 if self.docs[source].get("amended_from") else 1
			while f"{stem}-{counter}" in self.docs:
				counter += 1
			name = f"{stem}-{counter}"
		else:
			self._fresh += 1
			name = "TS-NEW" if self._fresh == 1 else f"TS-NEW-{self._fresh}"
			while name in self.docs:
				self._fresh += 1
				name = f"TS-NEW-{self._fresh}"
		doc.update(name=name, docstatus=0)
		doc.setdefault("time_logs", [])
		self._check_overlap(doc)
		self._fill(doc)
		state = self._workflow_state_for(0)
		if state and self.workflow:
			doc["workflow_state"] = state
		self._bump(doc)
		self.docs[name] = doc
		return copy.deepcopy(doc)

	def update_timesheet(self, name, payload, modified=None):
		self._enter("update", name, copy.deepcopy(payload))
		doc = self._guard(name, "write")
		if int(doc.get("docstatus") or 0) != 0:
			raise _error(f"Not allowed to change {name} after submission", "UpdateAfterSubmitError", 417)
		self._check_modified(doc, modified)
		changes = copy.deepcopy({key: value for key, value in payload.items() if key != "modified"})
		candidate = {**doc, **changes}
		self._check_overlap(candidate, ignore=name)
		doc.update(changes)
		self._fill(doc)
		self._bump(doc)
		return copy.deepcopy(doc)

	def submit_doc(self, doc):
		self._enter("submit", copy.deepcopy(doc))
		stored = self._guard(doc.get("name"), "submit")
		if int(stored.get("docstatus") or 0) != 0:
			raise _error(f"{stored['name']} is not a draft", "DocstatusTransitionError", 417)
		self._check_modified(stored, doc.get("modified"))
		stored["time_logs"] = copy.deepcopy(doc.get("time_logs") or [])
		stored["docstatus"] = 1
		state = self._workflow_state_for(1)
		if self.workflow and state:
			stored["workflow_state"] = state
		self._fill(stored)
		self._bump(stored)
		return copy.deepcopy(stored)

	def delete_timesheet(self, name):
		self._enter("delete", name)
		doc = self._guard(name, "delete")
		if int(doc.get("docstatus") or 0) != 0:
			raise _error(f"Submitted Document cannot be deleted: {name}", "ValidationError", 417)
		del self.docs[name]

	def cancel_timesheet(self, name):
		self._enter("cancel", name)
		if self.cancel_error:
			raise _error(self.cancel_error, "PermissionError", 403)
		doc = self._guard(name, "cancel")
		if int(doc.get("docstatus") or 0) != 1:
			raise _error(f"{name} is not submitted", "DocstatusTransitionError", 417)
		self._set_cancelled(doc)

	def _set_cancelled(self, doc: dict) -> None:
		doc["docstatus"] = 2
		state = self._workflow_state_for(2)
		if self.workflow and state:
			doc["workflow_state"] = state
		self._bump(doc)

	def apply_workflow(self, doc, action):
		self._enter("workflow", doc["name"], action)
		stored = self._require(doc["name"])
		options = self.workflow_transitions_unrecorded(stored)
		chosen = next((item for item in options if item.get("action") == action), None)
		if chosen is None:
			raise _error("Not a valid Workflow Action", "WorkflowTransitionError", 417)
		next_state = chosen.get("next_state")
		stored["workflow_state"] = next_state
		for state in (self.workflow or {}).get("states", []):
			if state["state"] == next_state:
				target = int(state.get("doc_status") or 0)
				if target == 2:
					self._set_cancelled(stored)
					return copy.deepcopy(stored)
				stored["docstatus"] = target
				break
		self._bump(stored)
		return copy.deepcopy(stored)

	def workflow_transitions_unrecorded(self, doc: dict) -> list:
		if isinstance(self.transitions, dict):
			return self.transitions.get(doc.get("workflow_state"), [])
		return self.transitions

	# Test helpers

	def bump_modified(self, name: str) -> str:
		"""Simulate a concurrent editor: the doc's `modified` changes without a client call."""
		self._bump(self._require(name))
		return self.docs[name]["modified"]

	def writes(self):
		return [call[0] for call in self.calls if call[0] not in READS]

	def reads(self):
		return [call[0] for call in self.calls if call[0] in READS]
