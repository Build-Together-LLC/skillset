"""Minimal Frappe REST client for any Frappe site. Stdlib only."""
from __future__ import annotations

import http.cookiejar
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from ts_common import SuiteError, build_opener, clean_credential, is_loopback_host, looks_like_secret


# Error classification. Order matters: specific exc_types, specific message substrings (English only —
# Frappe translates messages per user language), then the generic ValidationError, then the HTTP status.
_BY_EXC_TYPE = (
	("TimestampMismatchError", "conflict"),
	("LinkExistsError", "linked_docs"),
	("WorkflowPermissionError", "workflow_blocked"),
	("WorkflowTransitionError", "workflow_blocked"),
	("UpdateAfterSubmitError", "immutable_submitted"),
	("DocstatusTransitionError", "state_changed"),
	("PermissionError", "permission"),
	("DoesNotExistError", "not_found"),
	("AuthenticationError", "auth"),
)
_BY_MESSAGE = (
	("document has been modified after you have opened it", "conflict"),
	("is linked with", "linked_docs"),
	("cannot delete or cancel because", "linked_docs"),
	("self approval is not allowed", "workflow_blocked"),
	("not a valid workflow action", "workflow_blocked"),
	("not allowed to change", "immutable_submitted"),
	("cannot edit cancelled document", "state_changed"),
	("is overlapping with", "overlap"),
	("attendance is not marked", "attendance"),
	("not permitted", "permission"),
	("invalid login", "auth"),
	("could not find", "validation"),
	("value missing for", "validation"),
)
_GENERIC_EXC_TYPES = ("ValidationError", "MandatoryError", "InvalidStatusError", "LinkValidationError")
_BY_STATUS = ((401, "auth"), (403, "permission"), (404, "not_found"))


def classify(exc_type: str | None, status: int | None, message: str = "") -> str:
	"""Map a Frappe error to a stable code; see references/frappe_api.md for the table."""
	for name, code in _BY_EXC_TYPE:
		if exc_type == name:
			return code
	lowered = (message or "").lower()
	for needle, code in _BY_MESSAGE:
		if needle in lowered:
			return code
	if exc_type in _GENERIC_EXC_TYPES:
		return "validation"
	for number, code in _BY_STATUS:
		if status == number:
			return code
	if status is not None and status >= 500:
		return "server"
	return "error"


class FrappeError(SuiteError):
	"""A Frappe call failed.

	`status`: HTTP status (None when unreachable). `exc_type`: the raw Frappe `exc_type` (or None).
	`code`: the NORMALISED code (conflict, linked_docs, permission, not_found, validation, auth, unreachable,
	server, workflow_blocked, immutable_submitted, state_changed, overlap, redirect, workflow_unknown, error);
	derived from exc_type/status/message unless given. `detail`: the server message without request details.
	"""

	def __init__(
		self,
		message: str,
		*,
		code: str | None = None,
		status: int | None = None,
		exc_type: str | None = None,
		detail: str | None = None,
	):
		super().__init__(message)
		self.status = status
		self.exc_type = exc_type
		self.detail = message if detail is None else detail
		self.code = code or classify(exc_type, status, self.detail)


def server_message(payload: str) -> str:
	try:
		data = json.loads(payload)
	except ValueError:
		return payload.strip()[:300]
	if not isinstance(data, dict):
		return payload.strip()[:300]
	messages = []
	try:
		for raw in json.loads(data.get("_server_messages") or "[]"):
			item = json.loads(raw) if isinstance(raw, str) else raw
			messages.append(item.get("message", "") if isinstance(item, dict) else str(item))
	except (ValueError, TypeError):
		pass
	text = "; ".join(m for m in messages if m) or data.get("exception") or data.get("message") or payload[:300]
	return re.sub(r"<[^>]+>", "", str(text)).strip()


def exc_type(payload: str) -> str | None:
	try:
		data = json.loads(payload)
	except ValueError:
		return None
	value = data.get("exc_type") if isinstance(data, dict) else None
	return str(value) if value else None


class FrappeClient:
	"""Minimal Frappe REST client. Every failure is an `FrappeError`; request headers/bodies never enter a message.

	`opener` is injectable (tests, proxies). The default opener follows same-origin GET redirects only and, for a
	loopback site, ignores proxy environment variables.
	"""

	def __init__(
		self,
		site: str,
		*,
		api_key=None,
		api_secret=None,
		user=None,
		password=None,
		timeout=60,
		extra_handlers=(),
		opener=None,
	):
		self.site = site.rstrip("/")
		parts = urllib.parse.urlsplit(self.site)
		if parts.scheme != "https" and not (parts.scheme == "http" and is_loopback_host(parts.hostname or "")):
			raise SuiteError(f"Refusing to send credentials to {self.site} — use an https:// site (plain http only for localhost)")
		self.timeout = timeout
		self.headers = {"Accept": "application/json"}
		if opener is None:
			handlers = [urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), *extra_handlers]
			if is_loopback_host(parts.hostname or ""):
				handlers.append(urllib.request.ProxyHandler({}))
			opener = build_opener(self.site, True, handlers)
		self.opener = opener
		api_key = clean_credential(api_key, "FRAPPE_API_KEY")
		api_secret = clean_credential(api_secret, "FRAPPE_API_SECRET")
		user = clean_credential(user, "FRAPPE_USER")
		password = clean_credential(password, "FRAPPE_PASSWORD")
		if api_key and api_secret:
			self.headers["Authorization"] = f"token {api_key}:{api_secret}"
		elif user and password:
			self._request("POST", "/api/method/login", body={"usr": user, "pwd": password})
		else:
			raise SuiteError(
				"No Frappe credentials — set FRAPPE_API_KEY + FRAPPE_API_SECRET, "
				"or FRAPPE_USER + FRAPPE_PASSWORD"
			)

	@classmethod
	def from_env(cls, site: str) -> FrappeClient:
		env = os.environ
		return cls(
			site,
			api_key=env.get("FRAPPE_API_KEY"),
			api_secret=env.get("FRAPPE_API_SECRET"),
			user=env.get("FRAPPE_USER"),
			password=env.get("FRAPPE_PASSWORD"),
		)

	def _request(self, method: str, path: str, params: dict | None = None, body: dict | None = None) -> dict:
		url = self.site + path + ("?" + urllib.parse.urlencode(params) if params else "")
		data = json.dumps(body).encode() if body is not None else None
		request = urllib.request.Request(url, data=data, method=method, headers=dict(self.headers))
		if data is not None:
			request.add_header("Content-Type", "application/json")
		try:
			with self.opener.open(request, timeout=self.timeout) as response:
				raw = response.read().decode(errors="replace")
		except urllib.error.HTTPError as exc:
			payload = exc.read().decode(errors="replace")
			detail = server_message(payload)
			if looks_like_secret(detail):
				detail = "[redacted]"
			raise FrappeError(
				f"Frappe {method} {path} failed ({exc.code}): {detail}",
				status=exc.code,
				exc_type=exc_type(payload),
				detail=detail,
			) from None
		except urllib.error.URLError as exc:
			raise FrappeError(f"Could not reach {self.site}: {exc.reason}", code="unreachable") from None
		except FrappeError:
			raise
		except ValueError:
			# e.g. urllib rejecting a header value; its message can quote the Authorization header.
			raise FrappeError(f"Frappe {method} {path} could not be sent (invalid request)", code="error") from None
		except SuiteError as exc:
			raise FrappeError(str(exc), code="redirect") from None
		try:
			parsed = json.loads(raw or "{}")
		except ValueError:
			raise FrappeError(f"Frappe {method} {path} returned something that is not JSON", code="server") from None
		if not isinstance(parsed, dict):
			raise FrappeError(f"Frappe {method} {path} returned an unexpected payload", code="server")
		return parsed

	@staticmethod
	def _doc_path(doctype: str, name: str) -> str:
		return f"/api/resource/{urllib.parse.quote(doctype, safe='')}/{urllib.parse.quote(name, safe='')}"

	# Reads

	def list_docs(self, doctype: str, filters: list, fields: list, order_by: str | None = None) -> list[dict]:
		params = {"filters": json.dumps(filters), "fields": json.dumps(fields), "limit_page_length": 0}
		if order_by:
			params["order_by"] = order_by
		return self._request("GET", f"/api/resource/{urllib.parse.quote(doctype, safe='')}", params=params).get("data") or []

	def logged_user(self) -> str:
		return self._request("GET", "/api/method/frappe.auth.get_logged_user")["message"]

	def employees_for_user(self, user: str) -> list[dict]:
		return self.list_docs(
			"Employee",
			[["user_id", "=", user]],
			["name", "employee_name", "company", "department", "status"],
		)

	def timesheets_for(self, employee: str, date: str) -> list[dict]:
		return self.list_docs(
			"Timesheet",
			[["employee", "=", employee], ["start_date", "<=", date], ["end_date", ">=", date]],
			["name", "docstatus", "status", "start_date", "end_date", "total_hours", "modified"],
			order_by="modified desc",
		)

	def get_timesheet(self, name: str) -> dict:
		return self._request("GET", self._doc_path("Timesheet", name))["data"]

	def workflow_for(self, doctype: str, doc: dict | None = None) -> dict | None:
		"""The active workflow of `doctype` as `{name, document_type, workflow_state_field, states}`, or None.

		Reads `frappe.desk.form.load.getdoctype` (`__workflow_docs`), which any user who can read the doctype may
		call — the Workflow doctype itself is System-Manager-only, so listing it would say "none" for everyone else.
		FAILS CLOSED: any error, a malformed answer, or a doc carrying a `workflow_state` while detection says
		"no workflow" raises `FrappeError`; a 403 is never read as "no workflow".
		"""
		payload = self._request("GET", "/api/method/frappe.desk.form.load.getdoctype", params={"doctype": doctype})
		docs = payload.get("docs")
		if not isinstance(docs, list):
			raise FrappeError(f"Could not read the {doctype} workflow: unexpected getdoctype answer", code="server")
		found = None
		for meta in docs:
			if not isinstance(meta, dict) or meta.get("name") != doctype:
				continue
			for item in meta.get("__workflow_docs") or []:
				if isinstance(item, dict) and item.get("doctype") == "Workflow" and item.get("document_type") in (None, doctype):
					found = item
					break
		if found is None:
			if doc and doc.get("workflow_state"):
				raise FrappeError(
					f"{doctype} {doc.get('name')} has workflow state {doc['workflow_state']!r} but no workflow could be "
					"detected — refusing to guess",
					code="workflow_unknown",
				)
			return None
		return {
			"name": found.get("name"),
			"document_type": doctype,
			"workflow_state_field": found.get("workflow_state_field") or "workflow_state",
			"states": [
				{
					"state": state.get("state"),
					"doc_status": str(state.get("doc_status") if state.get("doc_status") is not None else "0"),
					"allow_edit": state.get("allow_edit"),
				}
				for state in found.get("states") or []
				if isinstance(state, dict)
			],
		}

	def has_permission(self, doctype: str, name: str, ptype: str) -> bool:
		"""True only when Frappe answers `has_permission: true`; anything else (including errors) is not True."""
		message = self._request(
			"GET",
			"/api/method/frappe.client.has_permission",
			params={"doctype": doctype, "docname": name, "perm_type": ptype},
		).get("message")
		if not isinstance(message, dict) or not isinstance(message.get("has_permission"), bool):
			raise FrappeError("Unexpected answer from frappe.client.has_permission", code="server")
		return message["has_permission"]

	def workflow_transitions(self, doc: dict) -> list[dict]:
		return (
			self._request(
				"POST", "/api/method/frappe.model.workflow.get_transitions", body={"doc": json.dumps(doc)}
			).get("message")
			or []
		)

	# Writes

	def create_timesheet(self, payload: dict) -> dict:
		return self._request("POST", "/api/resource/Timesheet", body=payload)["data"]

	def update_timesheet(self, name: str, payload: dict, modified: str) -> dict:
		"""PUT a draft. `modified` is the value read from the server, sent verbatim so Frappe can detect a stale write.

		Without it Frappe saves unconditionally (last write wins), so it is required.
		"""
		if not modified or not isinstance(modified, str):
			raise SuiteError("Refusing to update a timesheet without the `modified` value read from the server")
		return self._request("PUT", self._doc_path("Timesheet", name), body={**payload, "modified": modified})["data"]

	def submit_doc(self, doc: dict) -> dict:
		"""`frappe.client.submit` with the FULL document as read (a skeleton would make Frappe delete child rows)."""
		return self._request("POST", "/api/method/frappe.client.submit", body={"doc": json.dumps(doc)}).get("message")

	def delete_timesheet(self, name: str) -> None:
		self._request("DELETE", self._doc_path("Timesheet", name))

	def cancel_timesheet(self, name: str) -> None:
		self._request("POST", "/api/method/frappe.client.cancel", body={"doctype": "Timesheet", "name": name})

	def apply_workflow(self, doc: dict, action: str) -> dict:
		return self._request(
			"POST",
			"/api/method/frappe.model.workflow.apply_workflow",
			body={"doc": json.dumps(doc), "action": action},
		).get("message")
