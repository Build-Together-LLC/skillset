"""Timesheet lifecycle on a Frappe site: sync, update, amend, cancel, submit and pull. Stdlib only.

Every mutating command is a dry run unless it gets the one confirm flag that names what it is about to do
(`--confirm-create/-update/-cancel/-delete/-submit <token>`) and, for anything that changes an existing document,
`--expect-modified <timestamp>` copied from the dry run. Approvals are read from the command line only: never from the
environment or the profile. The flag is checked against the plan the live document actually produces, so approving
one action can never authorise another.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ts_common import (
	Env,
	SuiteError,
	config_dir,
	fmt_hours,
	out_dir_for,
	read_json,
	split_description,
	write_private_json,
)
from ts_frappe import FrappeError

DOCSTATUS_LABEL = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
PLAN_TEXT = {
	"create": "no timesheet covers this date — will create a new draft",
	"update": "draft {target} exists — will replace its rows, note and total",
	"cancel_and_amend": "{target} is submitted — will cancel it and create an amended draft that needs re-approval",
	"amend_cancelled": "only cancelled {target} exists — will create a draft amended from it",
	"ambiguous": "several active timesheets cover this date: {candidates}",
}
RESIDUAL_RISK = (
	"RISK: amending cancels the approved timesheet first. If the server then rejects the new draft, the cancelled "
	"timesheet stays cancelled and you must recreate the amendment by hand."
)
DRAFT_DELETE_WARNING = (
	"A DRAFT cannot be cancelled: this will DELETE it from the list (this tool cannot bring it back)."
)

HEADER_FIELDS = ("company", "employee", "note", "start_date", "end_date", "total_hours")
ROW_FIELDS = ("activity_type", "from_time", "to_time", "hours", "project", "description")
REMOTE_HEADER = (
	"name", "doctype", "modified", "docstatus", "workflow_state", "amended_from", "title", "company", "currency",
	"exchange_rate", "employee", "employee_name", "department", "start_date", "end_date", "total_hours", "note",
)
REMOTE_ROW = (
	"idx", "activity_type", "from_time", "to_time", "hours", "expected_hours", "project", "project_name",
	"description", "is_billable", "completed",
)
AUDIT_FIELDS = ("command", "site", "user", "doc", "status", "steps_done")
SPEC_SUMMARY_LIMIT = 200
MAX_NAME_IN_FILENAME = 100


# Errors


class LifecycleError(SuiteError):
	"""A lifecycle command stopped. `code` is machine readable; `steps_done` lists writes that already happened."""

	def __init__(self, message: str, *, code: str = "error", steps_done=(), exit_code: int | None = None):
		super().__init__(message)
		self.code = code
		self.steps_done = list(steps_done)
		if exit_code is not None:
			self.exit_code = exit_code


class ConfirmationRequired(LifecycleError):
	"""The user's approval for exactly this action is missing or does not match (exit 2: ask the user)."""

	exit_code = 2

	def __init__(self, message: str):
		super().__init__(message, code="confirmation_required")


def _needs(flag: str, expected, got) -> ConfirmationRequired:
	shown = "nothing" if got is None else repr(got)
	return ConfirmationRequired(f"needs --{flag} {expected} (got {shown}); ask the user, then re-run with exactly that")


def check_confirmation(
	flag: str, token: str, confirms: dict, *, modified: str | None = None, expect_modified: str | None = None
) -> bool:
	"""Decide whether the user approved THIS plan. False = dry run; raises `ConfirmationRequired` on any mismatch.

	`flag` is the action the live document actually calls for (`confirm-update`, ...); `confirms` maps every confirm
	flag the command accepts to the value given. A wrong token never degrades silently to a dry run.
	"""
	for other, value in confirms.items():
		if other != flag and value is not None:
			raise ConfirmationRequired(
				f"--{other} does not match the plan: this document needs --{flag} {token}. "
				"Nothing was written; ask the user about the actual plan"
			)
	given = confirms.get(flag)
	if given is None:
		return False
	if given != token:
		raise _needs(flag, token, given)
	if modified is not None:
		if expect_modified is None:
			raise _needs("expect-modified", repr(modified), None)
		if expect_modified != modified:
			conflict = ConfirmationRequired(
				f"{token} changed since it was read (modified {expect_modified} → {modified}). Nothing was written; "
				"run `pull` again and re-confirm with the user"
			)
			conflict.code = "conflict"
			raise conflict
	return True


# Audit


class AuditLog:
	"""One JSON line per applied mutation in `<config>/audit.log` (0600). A write failure warns; it never blocks."""

	def __init__(self, out: Callable[[str], None] = print):
		self.out = out

	def __call__(self, **fields) -> None:
		record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}
		record.update({key: fields[key] for key in AUDIT_FIELDS if key in fields})
		try:
			folder = config_dir()
			folder.mkdir(parents=True, exist_ok=True, mode=0o700)
			handle = os.open(folder / "audit.log", os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
			try:
				os.write(handle, (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8"))
			finally:
				os.close(handle)
		except OSError as exc:
			self.out(f"warning: could not write the audit log ({exc.strerror or exc})")


def _audit(audit, **fields) -> None:
	if audit is not None:
		audit(**fields)


# Plan, payload, cancel (moved from timesheet_suite.py)


def plan_sync(existing: list[dict]) -> dict:
	active = [sheet for sheet in existing if int(sheet.get("docstatus") or 0) < 2]
	cancelled = [sheet for sheet in existing if int(sheet.get("docstatus") or 0) == 2]
	if len(active) > 1:
		return {"action": "ambiguous", "candidates": [sheet["name"] for sheet in active]}
	if active:
		target = active[0]
		action = "update" if int(target.get("docstatus") or 0) == 0 else "cancel_and_amend"
		return {"action": action, "target": target["name"]}
	if cancelled:
		latest = max(cancelled, key=lambda sheet: str(sheet.get("modified") or ""))
		return {"action": "amend_cancelled", "target": latest["name"]}
	return {"action": "create", "target": None}


def write_payload(doc: dict, *, for_update: bool = False, amended_from: str | None = None) -> dict:
	"""A draft body for create/update: server-owned fields removed; `naming_series` never sent on create."""
	payload = json.loads(json.dumps(doc))
	payload["docstatus"] = 0
	for key in ("name", "status", "amended_from", "naming_series", "modified"):
		payload.pop(key, None)
	if for_update:
		for key in ("doctype", "docstatus"):
			payload.pop(key, None)
	if amended_from:
		payload["amended_from"] = amended_from
	for row in payload.get("time_logs") or []:
		for key in ("name", "parent", "parenttype", "parentfield"):
			row.pop(key, None)
	return payload


def _docstatus(doc: dict) -> int:
	return int(doc.get("docstatus") or 0)


def _states_with(workflow: dict | None, docstatus: int) -> set[str]:
	return {
		state["state"]
		for state in (workflow or {}).get("states") or []
		if str(state.get("doc_status")) == str(docstatus)
	}


def _expect_unchanged(doc: dict, expect_modified: str | None) -> None:
	if expect_modified is not None and doc.get("modified") != expect_modified:
		raise LifecycleError(
			f"{doc.get('name')} changed on the server since it was read (modified {expect_modified} → "
			f"{doc.get('modified')}). Nothing was written; run `pull` again",
			code="conflict",
		)


def cancel_submitted(client, name: str, out=print, *, expect_modified: str | None = None) -> None:
	"""Cancel directly; if the server refuses, use a workflow action that leads to a cancelled state.

	Direct cancel can bypass workflow transitions on some sites (existing behaviour, documented in frappe_api.md).
	Neither path has a server-side `modified` check, so the document is re-read and compared right before writing.
	"""
	current = client.get_timesheet(name)
	_expect_unchanged(current, expect_modified)
	try:
		client.cancel_timesheet(name)
	except SuiteError as direct:
		if getattr(direct, "code", None) in ("linked_docs", "unreachable"):
			raise
		out(f"Direct cancel refused ({direct}) — trying the Timesheet workflow")
		doc = client.get_timesheet(name)
		_expect_unchanged(doc, expect_modified)
		cancel_states = _states_with(client.workflow_for("Timesheet", doc), 2)
		options = [t for t in client.workflow_transitions(doc) if t.get("next_state") in cancel_states]
		if not options:
			raise LifecycleError(
				f"Could not cancel {name}: {direct}. No workflow action available to you cancels it — "
				"ask the approver to cancel or reopen it",
				code="workflow_blocked",
			) from None
		client.apply_workflow(doc, options[0]["action"])
	# From here the cancel has happened: whatever goes wrong next must still say so.
	try:
		cancelled = _docstatus(client.get_timesheet(name)) == 2
	except SuiteError as exc:
		raise LifecycleError(
			f"Cancel of {name} was sent but could not be verified ({exc}). Check it with `pull --name {name}` "
			"before doing anything else",
			code=getattr(exc, "code", "error"),
			steps_done=["cancel"],
		) from None
	if not cancelled:
		raise LifecycleError(
			f"{name} is still not cancelled — stopped before creating an amendment",
			code="state_changed",
			steps_done=["cancel"],
		)


# Remote documents: normalise and diff


def strip_html(text) -> str:
	"""Plain text of a Text Editor field: block ends become newlines, tags and entities are removed."""
	text = re.sub(r"(?i)<br\s*/?>|</(?:p|div|li|h[1-6])>", "\n", str(text or ""))
	text = html.unescape(re.sub(r"<[^>]+>", "", text))
	lines = [" ".join(line.split()) for line in text.splitlines()]
	return "\n".join(line for line in lines if line)


def normalise_remote(doc: dict) -> dict:
	"""The whitelisted header and row fields of a remote timesheet; owner/creation/costing noise is dropped."""
	remote = {key: doc[key] for key in REMOTE_HEADER if key in doc}
	rows = sorted(doc.get("time_logs") or [], key=lambda row: int(row.get("idx") or 0))
	remote["time_logs"] = [{key: row[key] for key in REMOTE_ROW if key in row} for row in rows]
	return remote


def _normalise(field: str, value):
	if field in ("from_time", "to_time"):
		return str(value or "")[:19]
	if field in ("start_date", "end_date"):
		return str(value or "")[:10]
	if field in ("hours", "total_hours"):
		return round(float(value or 0), 2)
	if field in ("note", "description"):
		return " ".join(strip_html(value).split())
	return "" if value is None else value


def diff_docs(remote: dict, new: dict) -> dict:
	"""Differences on the fields a rebuild controls only (the server recomputes costing and totals, so a full-document
	comparison would never be empty). Rows are paired by position."""
	header = {}
	for field in HEADER_FIELDS:
		before, after = _normalise(field, remote.get(field)), _normalise(field, new.get(field))
		if before != after:
			header[field] = [before, after]
	old_rows = sorted(remote.get("time_logs") or [], key=lambda row: int(row.get("idx") or 0))
	new_rows = list(new.get("time_logs") or [])
	changed = []
	for index, (old, fresh) in enumerate(zip(old_rows, new_rows), 1):
		fields = {}
		for field in ROW_FIELDS:
			before, after = _normalise(field, old.get(field)), _normalise(field, fresh.get(field))
			if before != after:
				fields[field] = [before, after]
		if fields:
			changed.append({"idx": index, **fields})
	rows = {
		"added": list(range(len(old_rows) + 1, len(new_rows) + 1)),
		"removed": list(range(len(new_rows) + 1, len(old_rows) + 1)),
		"changed": changed,
	}
	return {"header": header, "rows": rows, "empty": not (header or rows["added"] or rows["removed"] or changed)}


def _diff_lines(diff: dict) -> list[str]:
	lines = [f"  {field}: {before!r} → {after!r}" for field, (before, after) in diff["header"].items()]
	lines += [f"  row {index} added" for index in diff["rows"]["added"]]
	lines += [f"  row {index} removed" for index in diff["rows"]["removed"]]
	for row in diff["rows"]["changed"]:
		for field, pair in row.items():
			if field != "idx":
				lines.append(f"  row {row['idx']} {field}: {pair[0]!r} → {pair[1]!r}")
	return lines


# Shared steps


def _site_url(site: str, name: str) -> str:
	return f"{site.rstrip('/')}/app/timesheet/{urllib.parse.quote(name, safe='')}"


def _result(command: str, status: str, site: str, **fields) -> dict:
	return {"command": command, "status": status, "applied": False, "site": site, "warnings": [], **fields}


def _fill_final(result: dict, final: dict, site: str) -> dict:
	result.update(
		name=final["name"],
		docstatus=final.get("docstatus"),
		workflow_state=final.get("workflow_state"),
		total_hours=final.get("total_hours"),
		rows=len(final.get("time_logs") or []),
		modified=final.get("modified"),
		url=_site_url(site, final["name"]),
	)
	return result


def _announce_written(result: dict, out) -> None:
	out(
		f"Written: {result['name']} · docstatus {result['docstatus']} · workflow {result['workflow_state'] or '-'} · "
		f"{result['total_hours']}h · {result['rows']} rows"
	)
	out(result["url"])


def _dry_run(result: dict, out, flag: str, token: str, modified: str | None, extra: str = "") -> dict:
	"""The plan was printed; say exactly what approval would apply and return."""
	needs = f"--{flag} {token}" + (f" --expect-modified {modified!r}" if modified else "") + extra
	result.update(confirm_flag=flag, confirm_token=token, modified=modified, needs=needs)
	out(f"Dry run — nothing written. Ask the user in this conversation, then re-run with {needs}")
	return result


def check_identity(client, employee: str, out=print) -> str:
	"""The logged-in user's Employee must be `employee`: this tool edits your own timesheets only."""
	user = client.logged_user()
	employees = client.employees_for_user(user)
	if not any(item.get("name") == employee for item in employees):
		found = ", ".join(f"{e.get('name')} ({e.get('employee_name')})" for e in employees) or "no Employee record"
		raise LifecycleError(
			f"Logged in as {user} ({found}), not {employee} — check the credentials or the profile before writing",
			code="identity",
		)
	out(f"Site user: {user} → {employee}")
	return user


def _require_permission(client, name: str, ptype: str, what: str) -> None:
	"""Fail in the dry run, before the user is asked, when the role could not do it anyway."""
	if not client.has_permission("Timesheet", name, ptype):
		raise LifecycleError(
			f"You cannot {what} {name}: your role has no {ptype} permission on Timesheet. Nothing to retry; "
			"ask someone with the right role",
			code="permission",
		)


def _check_draft_input(doc: dict) -> None:
	if _docstatus(doc) != 0:
		raise LifecycleError("Only draft timesheets (docstatus 0) can be synced", code="validation")
	for field in ("employee", "start_date", "time_logs"):
		if not doc.get(field):
			raise LifecycleError(f"Timesheet JSON has no {field}", code="validation")


def _update_draft(
	client, doc: dict, remote: dict, *, command: str, site: str, user: str, plan: dict,
	confirm_update, expect_modified, out, audit,
) -> dict:
	name = remote["name"]
	_require_permission(client, name, "write", "edit")
	diff = diff_docs(normalise_remote(remote), doc)
	result = _result(command, "dry_run", site, **plan, name=name, diff=diff, modified=remote.get("modified"))
	proceed = check_confirmation(
		"confirm-update", name, {"confirm-update": confirm_update},
		modified=remote.get("modified"), expect_modified=expect_modified,
	)
	if diff["empty"]:
		out(f"{name} already matches this file — nothing to write.")
		result["status"] = "noop"
		return result
	out(f"Changes to {name}:")
	for line in _diff_lines(diff):
		out(line)
	if not proceed:
		return _dry_run(result, out, "confirm-update", name, remote.get("modified"))
	client.update_timesheet(name, write_payload(doc, for_update=True), modified=remote.get("modified"))
	final = client.get_timesheet(name)
	result.update(status="applied", applied=True)
	_fill_final(result, final, site)
	_announce_written(result, out)
	_audit(audit, command=command, site=site, user=user, doc=name, status="applied")
	return result


# Preflight


def preflight_references(client, doc: dict) -> list[str]:
	"""Activity Types and Projects the new draft names must exist: cheap to check now, costly to learn after a cancel.

	Returns warnings for lookups the role may not read; raises when a name is definitely missing."""
	warnings, missing = [], []
	for doctype, field in (("Activity Type", "activity_type"), ("Project", "project")):
		wanted = sorted({row.get(field) for row in doc.get("time_logs") or [] if row.get(field)})
		if not wanted:
			continue
		try:
			found = {item["name"] for item in client.list_docs(doctype, [["name", "in", wanted]], ["name"])}
		except FrappeError as exc:
			warnings.append(f"could not verify {doctype} names ({exc.code}); the server may still reject them")
			continue
		missing += [f"{doctype} {name!r}" for name in wanted if name not in found]
	if missing:
		raise LifecycleError(
			f"The new draft names {', '.join(missing)}, which the site does not have. Nothing was changed; "
			"fix the spec and rebuild",
			code="validation",
		)
	return warnings


def preflight_overlaps(client, doc: dict, exclude=()) -> list[str]:
	"""Best effort: other active timesheets of the employee whose rows overlap the new rows (server rules still apply)."""
	hits = []
	for sheet in client.timesheets_for(doc["employee"], doc["start_date"]):
		if sheet["name"] in exclude or _docstatus(sheet) == 2:
			continue
		other = client.get_timesheet(sheet["name"])
		for mine in doc.get("time_logs") or []:
			for theirs in other.get("time_logs") or []:
				if str(mine["from_time"]) < str(theirs.get("to_time") or "") and str(theirs.get("from_time") or "") < str(
					mine["to_time"]
				):
					hits.append(f"{other['name']} (row {theirs.get('idx', '?')})")
	return sorted(set(hits))


def _cancelled_leaf(client, source: dict) -> dict:
	"""Follow the amended_from chain from a cancelled timesheet to its newest cancelled descendant."""
	current = source
	for _ in range(50):
		children = client.list_docs(
			"Timesheet", [["amended_from", "=", current["name"]]], ["name", "docstatus", "modified"]
		)
		active = [child["name"] for child in children if _docstatus(child) < 2]
		if active:
			raise LifecycleError(
				f"{active[0]} already amends {source['name']} — use `update {active[0]} <timesheet.json>` instead",
				code="duplicate_amendment",
			)
		if not children:
			return current
		current = client.get_timesheet(max(children, key=lambda child: str(child.get("modified") or ""))["name"])
	raise LifecycleError(f"{source['name']} has an implausibly long amendment chain", code="error")


# Commands (Python API)


def run_sync(
	client, doc: dict, *, site: str, confirm_create=None, confirm_update=None, expect_modified=None,
	out=print, audit=None,
) -> dict:
	"""Create the day's draft or overwrite it. Submitted or cancelled sheets are never touched here: use `amend`."""
	_check_draft_input(doc)
	user = check_identity(client, doc["employee"], out)
	existing = client.timesheets_for(doc["employee"], doc["start_date"])
	for sheet in existing:
		out(
			f"  found {sheet['name']} · {DOCSTATUS_LABEL.get(_docstatus(sheet))} · "
			f"{sheet.get('start_date')} → {sheet.get('end_date')} · "
			f"{fmt_hours(float(sheet.get('total_hours') or 0))}h"
		)
	plan = plan_sync(existing)
	out(
		"Plan: "
		+ PLAN_TEXT[plan["action"]].format(target=plan.get("target"), candidates=", ".join(plan.get("candidates", [])))
	)
	if plan["action"] == "ambiguous":
		raise LifecycleError(
			"Several active timesheets cover this date — ask which one to update", code="ambiguous", exit_code=2
		)
	confirms = {"confirm-create": confirm_create, "confirm-update": confirm_update}
	if plan["action"] == "create":
		token = f"{doc['employee']}/{doc['start_date']}"
		result = _result("sync", "dry_run", site, **plan)
		if not check_confirmation("confirm-create", token, confirms):
			return _dry_run(result, out, "confirm-create", token, None)
		try:
			created = client.create_timesheet(write_payload(doc))
		except FrappeError as exc:
			if exc.code == "attendance":
				raise LifecycleError(
					f"The site refuses a timesheet for {doc['start_date']} because attendance is not marked Present "
					f"for {doc['employee']} on that day (the 'weekly_off_based_on' text in the server message is a side "
					"effect, not a second problem). Nothing was written and retrying will not help. Ask HR to mark "
					"attendance Present or approve an Attendance Request for that date, then re-run the same confirm "
					"command; or move the hours to a day that has attendance",
					code="attendance",
				) from None
			raise
		final = client.get_timesheet(created["name"])
		result.update(status="applied", applied=True)
		_fill_final(result, final, site)
		_announce_written(result, out)
		_audit(audit, command="sync", site=site, user=user, doc=final["name"], status="created")
		return result
	if plan["action"] == "update":
		return _update_draft(
			client, doc, client.get_timesheet(plan["target"]), command="sync", site=site, user=user, plan=plan,
			confirm_update=confirm_update if confirm_create is None else _refuse_flag("confirm-create", plan),
			expect_modified=expect_modified, out=out, audit=audit,
		)
	if any(value is not None for value in confirms.values()):
		raise ConfirmationRequired(
			f"sync never cancels or amends: {plan['target']} needs `amend`, not a --confirm flag on sync"
		)
	out(f"sync does not touch {plan['target']} — use `amend {plan['target']} <timesheet.json>` (dry run first).")
	return _result("sync", "use_amend", site, **plan, needs=f"amend {plan['target']} <timesheet.json>")


def _refuse_flag(flag: str, plan: dict):
	raise ConfirmationRequired(
		f"--{flag} does not match the plan: draft {plan['target']} needs --confirm-update {plan['target']}. "
		"Nothing was written; ask the user about the actual plan"
	)


def run_update(
	client, name: str, doc: dict, *, site: str, confirm_update=None, expect_modified=None, out=print, audit=None
) -> dict:
	"""Overwrite the named DRAFT with this file. Submitted/cancelled documents are refused: use `amend`."""
	_check_draft_input(doc)
	remote = client.get_timesheet(name)
	if _docstatus(remote) != 0:
		raise LifecycleError(
			f"{name} is {DOCSTATUS_LABEL.get(_docstatus(remote), 'not a draft').lower()} — use `amend {name} <timesheet.json>`",
			code="state_changed",
		)
	if remote.get("employee") != doc["employee"]:
		raise LifecycleError(
			f"{name} belongs to {remote.get('employee')} but the file is for {doc['employee']}; refusing to move it",
			code="validation",
		)
	user = check_identity(client, remote["employee"], out)
	return _update_draft(
		client, doc, remote, command="update", site=site, user=user, plan={"action": "update", "target": name},
		confirm_update=confirm_update, expect_modified=expect_modified, out=out, audit=audit,
	)


def run_amend(
	client, name: str, doc: dict, *, site: str, confirm_cancel=None, confirm_create=None, expect_modified=None,
	out=print, audit=None,
) -> dict:
	"""Replace a submitted timesheet (cancel, then a new amended draft) or amend a cancelled one (create only)."""
	_check_draft_input(doc)
	source = client.get_timesheet(name)
	if source.get("employee") != doc["employee"]:
		raise LifecycleError(
			f"{name} belongs to {source.get('employee')} but the file is for {doc['employee']}; refusing to amend it",
			code="validation",
		)
	user = check_identity(client, source["employee"], out)
	status = _docstatus(source)
	if status == 0:
		raise LifecycleError(f"{name} is a draft — use `update {name} <timesheet.json>`", code="state_changed")
	if status == 1:
		action, flag, current = "cancel_and_amend", "confirm-cancel", source
	else:
		action, flag, current = "amend_cancelled", "confirm-create", _cancelled_leaf(client, source)
	token = name
	plan = {"action": action, "target": current["name"]}
	out("Plan: " + PLAN_TEXT[action].format(target=current["name"]))
	warnings = preflight_references(client, doc)
	overlaps = preflight_overlaps(client, doc, exclude={name})
	if overlaps:
		raise LifecycleError(
			f"The new rows overlap {', '.join(overlaps)}. Nothing was changed; fix the times first", code="overlap"
		)
	if status == 1:
		_require_permission(client, name, "cancel", "cancel")
		out(RESIDUAL_RISK)
	result = _result("amend", "dry_run", site, **plan, warnings=warnings, steps_done=[])
	proceed = check_confirmation(
		flag, token, {"confirm-cancel": confirm_cancel, "confirm-create": confirm_create},
		modified=current.get("modified"), expect_modified=expect_modified,
	)
	if not proceed:
		return _dry_run(result, out, flag, token, current.get("modified"))
	steps: list[str] = []
	creating = False
	try:
		if status == 1:
			try:
				cancel_submitted(client, name, out, expect_modified=current.get("modified"))
			except LifecycleError as exc:
				steps = list(exc.steps_done)  # the cancel went through even if verifying it did not
				raise
			steps.append("cancel")
		creating = True
		written = client.create_timesheet(write_payload(doc, amended_from=current["name"]))
	except SuiteError as exc:
		steps = steps or list(getattr(exc, "steps_done", []))
		_audit(audit, command="amend", site=site, user=user, doc=name, status="partial" if steps else "failed", steps_done=steps)
		if not steps:
			raise
		if not creating:
			raise
		raise LifecycleError(
			f"{name} is cancelled but the amendment was rejected: {exc}. No amendment exists; fix the problem and re-run "
			f"`amend {name} <timesheet.json>` (it will create only); the local JSON is untouched",
			code=getattr(exc, "code", "error"),
			steps_done=steps,
		) from None
	steps.append("create")
	final = client.get_timesheet(written["name"])
	result.update(status="applied", applied=True, steps_done=steps, created=final["name"])
	_fill_final(result, final, site)
	_announce_written(result, out)
	_audit(audit, command="amend", site=site, user=user, doc=name, status="applied", steps_done=steps)
	return result


def run_cancel(
	client, name: str, *, site: str, confirm_cancel=None, confirm_delete=None, expect_modified=None,
	out=print, audit=None,
) -> dict:
	"""Cancel a submitted timesheet, or DELETE a draft (a different flag, so one approval never covers the other)."""
	remote = client.get_timesheet(name)
	user = check_identity(client, remote["employee"], out)
	status = _docstatus(remote)
	modified = remote.get("modified")
	base = {"name": name, "docstatus_before": status}
	if status == 2:
		out(f"{name} is already cancelled — nothing to do.")
		return _result("cancel", "already_cancelled", site, **base, docstatus_after=2)
	confirms = {"confirm-cancel": confirm_cancel, "confirm-delete": confirm_delete}
	if status == 1:
		_require_permission(client, name, "cancel", "cancel")
		out(f"Plan: cancel submitted {name} (it can be amended afterwards).")
		result = _result("cancel", "dry_run", site, **base, plan=["cancel"])
		if not check_confirmation("confirm-cancel", name, confirms, modified=modified, expect_modified=expect_modified):
			return _dry_run(result, out, "confirm-cancel", name, modified)
		try:
			cancel_submitted(client, name, out, expect_modified=modified)
			final = client.get_timesheet(name)
		except SuiteError as exc:
			if getattr(exc, "steps_done", None):
				_audit(audit, command="cancel", site=site, user=user, doc=name, status="partial", steps_done=list(exc.steps_done))
			raise
		result.update(status="applied", applied=True, docstatus_after=_docstatus(final))
		_fill_final(result, final, site)
		out(f"Cancelled {name}.")
		_audit(audit, command="cancel", site=site, user=user, doc=name, status="cancelled")
		return result
	_require_permission(client, name, "delete", "delete")
	out(f"Plan: {DRAFT_DELETE_WARNING}")
	result = _result("cancel", "dry_run", site, **base, plan=["delete"])
	if not check_confirmation("confirm-delete", name, confirms, modified=modified, expect_modified=expect_modified):
		return _dry_run(result, out, "confirm-delete", name, modified)
	_expect_unchanged(client.get_timesheet(name), modified)  # deleting has no server-side timestamp check
	try:
		client.delete_timesheet(name)
	except FrappeError as exc:
		if exc.code != "not_found":
			raise
	try:
		client.get_timesheet(name)
	except FrappeError as exc:
		if exc.code != "not_found":
			raise
	else:
		raise LifecycleError(f"{name} still exists after the delete call", code="unexpected_state")
	result.update(status="applied", applied=True, docstatus_after=None)
	out(f"Deleted draft {name}.")
	_audit(audit, command="cancel", site=site, user=user, doc=name, status="deleted")
	return result


def _submit_options(client, doc: dict, workflow: dict, action: str | None) -> tuple[str, str, str]:
	"""(action, next_state, next docstatus) for the one workflow action a submit approval may cover (docstatus 0/1 only)."""
	docstatus_of = {state["state"]: str(state.get("doc_status")) for state in workflow.get("states") or []}
	allowed = [
		item for item in client.workflow_transitions(doc) if docstatus_of.get(item.get("next_state")) in ("0", "1")
	]
	submitting = [item for item in allowed if docstatus_of[item["next_state"]] == "1"]
	pool = submitting or allowed
	if action is not None:
		pool = [item for item in allowed if item.get("action") == action]
		if not pool:
			raise LifecycleError(
				f"Workflow action {action!r} is not available here or does not lead to a draft/submitted state "
				f"(allowed: {', '.join(item['action'] for item in allowed) or 'none'})",
				code="workflow_blocked",
			)
	if not pool:
		raise LifecycleError(
			"No workflow action available to you submits this timesheet. Frappe hides actions you may not take "
			"(including self-approval when the workflow forbids it) — ask the approver",
			code="workflow_blocked",
		)
	if len(pool) > 1:
		raise LifecycleError(
			f"Several workflow actions apply ({', '.join(item['action'] for item in pool)}); pick one with --action",
			code="ambiguous",
			exit_code=2,
		)
	item = pool[0]
	return item["action"], item["next_state"], docstatus_of[item["next_state"]]


def run_submit(
	client, name: str, *, site: str, confirm_submit=None, expect_modified=None, action=None, out=print, audit=None
) -> dict:
	"""Submit a draft: plain `frappe.client.submit` only when the site has NO workflow, else one echoed workflow action."""
	doc = client.get_timesheet(name)
	user = check_identity(client, doc["employee"], out)
	status = _docstatus(doc)
	base = {"name": name, "docstatus_before": status}
	if status == 1:
		out(f"{name} is already submitted — nothing to do.")
		return _result("submit", "already_submitted", site, **base, docstatus_after=1, submitted=True)
	if status == 2:
		raise LifecycleError(f"{name} is cancelled — amend it first", code="state_changed")
	if not doc.get("time_logs") or float(doc.get("total_hours") or 0) <= 0:
		raise LifecycleError(f"{name} has no hours to submit", code="validation")
	workflow = client.workflow_for("Timesheet", doc)
	modified = doc.get("modified")
	if workflow is None:
		_require_permission(client, name, "submit", "submit")
		via, chosen, next_status = "submit", None, "1"
		out(f"Plan: submit {name} ({fmt_hours(float(doc['total_hours']))}h, {len(doc['time_logs'])} rows).")
	else:
		chosen, next_state, next_status = _submit_options(client, doc, workflow, action)
		via = "workflow"
		verdict = "SUBMITTED" if next_status == "1" else "NOT submitted — an approver must finish it"
		out(f"Plan: workflow action {chosen!r}: {doc.get('workflow_state') or '-'} → {next_state}; {verdict}.")
	result = _result(
		"submit", "dry_run", site, **base, plan=[via if chosen is None else f"workflow:{chosen}"], via=via,
		action=chosen, submitted=False,
	)
	if not check_confirmation(
		"confirm-submit", name, {"confirm-submit": confirm_submit}, modified=modified, expect_modified=expect_modified
	):
		return _dry_run(result, out, "confirm-submit", name, modified, f" --action {chosen!r}" if chosen else "")
	if via == "workflow" and action != chosen:
		raise _needs("action", repr(chosen), action)
	if via == "submit":
		client.submit_doc(doc)
	else:
		fresh = client.get_timesheet(name)
		_expect_unchanged(fresh, modified)
		client.apply_workflow(fresh, chosen)
	final = client.get_timesheet(name)
	if next_status == "1":
		if _docstatus(final) != 1:
			raise LifecycleError(
				f"The server accepted the request but {name} is still docstatus {_docstatus(final)} "
				f"(workflow {final.get('workflow_state') or '-'})",
				code="unexpected_state",
			)
		result.update(status="applied", submitted=True)
	else:
		if final.get("workflow_state") == doc.get("workflow_state") and final.get("modified") == modified:
			raise LifecycleError(f"{name} did not change after the workflow action", code="unexpected_state")
		result.update(status="pending_approval", submitted=False)
		out(f"{name} moved to {final.get('workflow_state')}; it is NOT submitted until an approver acts.")
	result.update(applied=True, docstatus_after=_docstatus(final))
	_fill_final(result, final, site)
	_announce_written(result, out)
	_audit(audit, command="submit", site=site, user=user, doc=name, status=result["status"])
	return result


# Pull


def _link_label(url: str) -> str:
	parts = urllib.parse.urlsplit(url)
	for pattern, fmt in ((r"/pull/(\d+)", "PR-{}"), (r"/issues/(\d+)", "#{}")):
		match = re.search(pattern, parts.path)
		if match:
			return fmt.format(match.group(1))
	return parts.hostname or url


def spec_from_remote(doc: dict, site: str) -> tuple[dict, list[str]]:
	"""An editable spec for `build` from a remote timesheet. Jira lines stay verbatim in the text; only http(s) `Ref:`
	lines become links; hours and projects are pinned so a profile default can never silently re-home a row."""
	remote = normalise_remote(doc)
	rows = remote["time_logs"]
	warnings = []
	if _docstatus(doc) != 0:
		warnings.append(f"{doc['name']} is {DOCSTATUS_LABEL[_docstatus(doc)].lower()}: editing it means `amend`, not `update`")
	previous_end = None
	for row in rows:
		if previous_end is not None and str(row.get("from_time") or "")[:19] != previous_end:
			warnings.append("rows are not back to back; a rebuild re-derives times from the start time")
			break
		previous_end = str(row.get("to_time") or "")[:19]
	entries = []
	for row in rows:
		text, links = split_description(row.get("description"))
		entries.append(
			{
				"label": row.get("activity_type"),
				"activity_type": row.get("activity_type"),
				"hours": round(float(row.get("hours") or 0), 2),
				"summary": " ".join(text.split())[:SPEC_SUMMARY_LIMIT],
				"description": text,
				"links": [{"label": _link_label(link["url"]), "url": link["url"]} for link in links],
				"tickets": [],
				"project": row.get("project"),
				"project_name": row.get("project_name"),
			}
		)
	warnings.append("chat summaries are rebuilt from the descriptions; the original chat wording is not stored remotely")
	start = str(rows[0].get("from_time") or "")[11:19] if rows else ""
	spec = {
		"source": {
			"name": doc["name"],
			"modified": doc.get("modified"),
			"docstatus": _docstatus(doc),
			"workflow_state": doc.get("workflow_state"),
			"employee": doc.get("employee"),
			"site": site,
		},
		"date": str(doc.get("start_date") or "")[:10],
		"start_time": start[:5] or None,
		"target_total_hours": None,
		"note": strip_html(doc.get("note")),
		"entries": entries,
	}
	return spec, warnings


def run_pull(
	client, *, site: str, out_dir, name=None, date=None, employee=None, profile_employee=None, out=print
) -> dict:
	"""Read a remote timesheet back into `remote_<name>.json` and `edit_<name>.spec.json`. Writes nothing remotely."""
	if bool(name) == bool(date):
		raise LifecycleError("pull needs exactly one of --name or --date", code="validation", exit_code=2)
	if name is None:
		who = employee or profile_employee
		if not who:
			raise LifecycleError("pull --date needs an employee (profile or --employee)", code="validation", exit_code=2)
		sheets = client.timesheets_for(who, date)
		active = [sheet for sheet in sheets if _docstatus(sheet) < 2]
		if len(active) > 1:
			lines = "; ".join(
				f"{s['name']} · {DOCSTATUS_LABEL[_docstatus(s)]} · {fmt_hours(float(s.get('total_hours') or 0))}h · {s.get('modified')}"
				for s in active
			)
			raise LifecycleError(f"Several active timesheets cover {date}: {lines}. Re-run with --name", code="ambiguous", exit_code=2)
		pool = active or [s for s in sheets if _docstatus(s) == 2]
		if not pool:
			raise LifecycleError(f"No timesheet covers {date} for {who}", code="not_found")
		name = max(pool, key=lambda sheet: str(sheet.get("modified") or ""))["name"]
	doc = client.get_timesheet(name)
	spec, warnings = spec_from_remote(doc, site)
	folder = Path(out_dir)
	safe = urllib.parse.quote(name, safe="")
	if len(safe) > MAX_NAME_IN_FILENAME:
		safe = f"{safe[:MAX_NAME_IN_FILENAME]}-{hashlib.sha256(name.encode()).hexdigest()[:8]}"
	remote_path, spec_path = folder / f"remote_{safe}.json", folder / f"edit_{safe}.spec.json"
	try:
		write_private_json(remote_path, normalise_remote(doc))
		write_private_json(spec_path, spec)
	except OSError as exc:
		raise LifecycleError(f"Could not write the pulled files into {folder}: {exc.strerror or exc}", code="error") from None
	hours = fmt_hours(float(doc.get("total_hours") or 0))
	out(
		f"{name} · {DOCSTATUS_LABEL.get(_docstatus(doc))} · workflow {doc.get('workflow_state') or '-'} · {hours}h · "
		f"{len(doc.get('time_logs') or [])} rows · modified {doc.get('modified')}"
	)
	out(f"remote: {remote_path}")
	out(f"spec:   {spec_path}")
	for warning in warnings:
		out(f"warning: {warning}")
	return _result(
		"pull", "pulled", site, name=name, docstatus=_docstatus(doc), modified=doc.get("modified"), total_hours=doc.get("total_hours"),
		rows=len(doc.get("time_logs") or []), remote=str(remote_path), spec=str(spec_path), warnings=warnings,
	)


# CLI


def _error_result(command: str, exc: SuiteError) -> dict:
	return {
		"command": command,
		"status": "error",
		"applied": False,
		"code": getattr(exc, "code", "error"),
		"message": str(exc),
		"steps_done": list(getattr(exc, "steps_done", [])),
	}


def _common(parser: argparse.ArgumentParser, *, expect_modified: bool = True) -> None:
	if expect_modified:
		parser.add_argument("--expect-modified", help="the `modified` value the dry run printed (required with a confirm flag)")
	parser.add_argument("--json", action="store_true", help="machine result on stdout, human lines on stderr")


def add_parsers(commands) -> dict[str, Callable[[argparse.Namespace, Env], int]]:
	sync = commands.add_parser("sync", help="create or overwrite the day's DRAFT on the site (dry run by default)", allow_abbrev=False)
	sync.add_argument("timesheet", help="timesheet_<date>.json written by `build`")
	sync.add_argument("--confirm-create", help="the confirm_token the dry run printed")
	sync.add_argument("--confirm-update", help="the draft's name, to overwrite it")
	_common(sync)

	update = commands.add_parser("update", help="overwrite a DRAFT with a rebuilt timesheet", allow_abbrev=False)
	update.add_argument("name")
	update.add_argument("timesheet")
	update.add_argument("--confirm-update", help="the draft's name")
	_common(update)

	amend = commands.add_parser(
		"amend", help="submitted -> cancel + new amended draft; cancelled -> new amended draft", allow_abbrev=False
	)
	amend.add_argument("name")
	amend.add_argument("timesheet")
	amend.add_argument("--confirm-cancel", help="the submitted timesheet's name (cancels it, then creates the draft)")
	amend.add_argument("--confirm-create", help="the cancelled timesheet's name (creates the draft only)")
	_common(amend)

	cancel = commands.add_parser("cancel", help="cancel a submitted timesheet, or delete a draft", allow_abbrev=False)
	cancel.add_argument("name")
	cancel.add_argument("--confirm-cancel", help="the submitted timesheet's name")
	cancel.add_argument("--confirm-delete", help="the DRAFT's name (permanent removal)")
	_common(cancel)

	submit = commands.add_parser("submit", help="submit a draft (asks every time; separate from saving)", allow_abbrev=False)
	submit.add_argument("name")
	submit.add_argument("--confirm-submit", help="the timesheet's name")
	submit.add_argument("--action", help="workflow action to apply when several are possible")
	_common(submit)

	pull = commands.add_parser("pull", help="read a remote timesheet back as an editable spec (read-only)", allow_abbrev=False)
	group = pull.add_mutually_exclusive_group()
	group.add_argument("--name")
	group.add_argument("--date")
	pull.add_argument("--employee")
	pull.add_argument("--out-dir")
	_common(pull, expect_modified=False)

	def runner(command: str):
		def handle(args: argparse.Namespace, env: Env) -> int:
			as_json = bool(getattr(args, "json", False))
			out = (lambda line: print(line, file=sys.stderr)) if as_json else env.out
			try:
				profile = env.load_profile()
				site = profile["site"]
				out(f"site: {site}")
				client = env.client_factory(site)
				audit = AuditLog(out)
				result = _dispatch(command, args, client, profile, site, out, audit)
			except SuiteError as exc:
				print(f"error: {exc}", file=sys.stderr)
				if as_json:
					print(json.dumps(_error_result(command, exc), ensure_ascii=False))
				return getattr(exc, "exit_code", 1)
			if as_json:
				print(json.dumps(result, ensure_ascii=False))
			return 0

		return handle

	return {name: runner(name) for name in ("sync", "update", "amend", "cancel", "submit", "pull")}


def _dispatch(command: str, args, client, profile: dict, site: str, out, audit) -> dict:
	expect = getattr(args, "expect_modified", None)
	if command == "sync":
		return run_sync(
			client, read_json(args.timesheet), site=site, confirm_create=args.confirm_create,
			confirm_update=args.confirm_update, expect_modified=expect, out=out, audit=audit,
		)
	if command == "update":
		return run_update(
			client, args.name, read_json(args.timesheet), site=site, confirm_update=args.confirm_update,
			expect_modified=expect, out=out, audit=audit,
		)
	if command == "amend":
		return run_amend(
			client, args.name, read_json(args.timesheet), site=site, confirm_cancel=args.confirm_cancel,
			confirm_create=args.confirm_create, expect_modified=expect, out=out, audit=audit,
		)
	if command == "cancel":
		return run_cancel(
			client, args.name, site=site, confirm_cancel=args.confirm_cancel, confirm_delete=args.confirm_delete,
			expect_modified=expect, out=out, audit=audit,
		)
	if command == "submit":
		return run_submit(
			client, args.name, site=site, confirm_submit=args.confirm_submit, expect_modified=expect,
			action=args.action, out=out, audit=audit,
		)
	return run_pull(
		client, site=site, out_dir=out_dir_for(profile, args.out_dir), name=args.name, date=args.date,
		employee=args.employee, profile_employee=profile.get("employee"), out=out,
	)
