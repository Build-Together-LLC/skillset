"""Unit tests for ts_frappe.py and the shared FakeClient. Run from the skill folder:

    python3 -m unittest discover -s scripts -p 'test_ts_frappe*.py'
"""
from __future__ import annotations

import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ts_common  # noqa: E402
import ts_frappe  # noqa: E402
from ts_fakes import FakeClient  # noqa: E402
from ts_frappe import FrappeError  # noqa: E402

SECRET = "sekrit-" + "9f3a1c77"


class Response:
	def __init__(self, payload):
		self.payload = payload if isinstance(payload, str) else json.dumps(payload)

	def read(self):
		return self.payload.encode()

	def __enter__(self):
		return self

	def __exit__(self, *exc):
		return False


class ScriptedOpener:
	"""Stands in for urllib's opener: records requests, answers from a queue (a dict/str payload or an exception)."""

	def __init__(self, *answers):
		self.answers = list(answers)
		self.requests = []

	def open(self, request, timeout=None):
		self.requests.append(request)
		answer = self.answers.pop(0)
		if isinstance(answer, Exception):
			raise answer
		return Response(answer)


def http_error(status, payload):
	body = payload if isinstance(payload, str) else json.dumps(payload)
	return urllib.error.HTTPError("https://x/y", status, "err", {}, io.BytesIO(body.encode()))


def client_with(*answers, **kwargs):
	opener = ScriptedOpener(*answers)
	client = ts_frappe.FrappeClient("https://erp.example.com", api_key="k", api_secret=SECRET, opener=opener, **kwargs)
	return client, opener


def getdoctype(*workflow_docs, name="Timesheet"):
	return {"docs": [{"name": name, "__workflow_docs": list(workflow_docs)}]}


WORKFLOW_DOC = {
	"doctype": "Workflow",
	"name": "Timesheet Approval",
	"document_type": "Timesheet",
	"workflow_state_field": "workflow_state",
	"states": [
		{"state": "Draft", "doc_status": "0", "allow_edit": "Employee"},
		{"state": "Approved", "doc_status": "1", "allow_edit": "Projects Manager"},
		{"state": "Cancelled", "doc_status": 2},
	],
}


class ServerMessageTests(unittest.TestCase):
	def test_extracts_frappe_server_messages(self):
		payload = json.dumps(
			{
				"exception": "frappe.exceptions.ValidationError",
				"_server_messages": json.dumps([json.dumps({"message": "Row 1: <b>overlapping</b> with TS-9"})]),
			}
		)
		self.assertEqual(ts_frappe.server_message(payload), "Row 1: overlapping with TS-9")

	def test_falls_back_to_the_exception_or_raw_text(self):
		self.assertEqual(ts_frappe.server_message(json.dumps({"exception": "PermissionError"})), "PermissionError")
		self.assertEqual(ts_frappe.server_message("Bad Gateway"), "Bad Gateway")


class ClientTests(unittest.TestCase):
	def test_requires_credentials_from_the_environment(self):
		with mock.patch.dict(os.environ, {}, clear=True):
			with self.assertRaisesRegex(ts_common.SuiteError, "FRAPPE_API_KEY"):
				ts_frappe.FrappeClient.from_env("https://erp.example.com")

	def test_api_key_is_sent_as_a_token_header(self):
		with mock.patch.dict(os.environ, {"FRAPPE_API_KEY": "k", "FRAPPE_API_SECRET": "s"}, clear=True):
			client = ts_frappe.FrappeClient.from_env("https://erp.example.com/")
		self.assertEqual(client.headers["Authorization"], "token k:s")
		self.assertEqual(client.site, "https://erp.example.com")

	def test_credentials_are_never_sent_over_plain_http_to_a_remote_host(self):
		with self.assertRaisesRegex(ts_common.SuiteError, "https"):
			ts_frappe.FrappeClient("http://erp.example.com", api_key="k", api_secret="s")


class CredentialHygieneTests(unittest.TestCase):
	def test_env_secret_with_trailing_newline_is_cleaned_and_sent_intact(self):
		env = {"FRAPPE_API_KEY": "k\n", "FRAPPE_API_SECRET": SECRET + "\r\n"}
		with mock.patch.dict(os.environ, env, clear=True):
			client = ts_frappe.FrappeClient.from_env("https://erp.example.com")
		self.assertEqual(client.headers["Authorization"], f"token k:{SECRET}")

	def test_control_characters_inside_a_credential_raise_without_echoing_it(self):
		env = {"FRAPPE_API_KEY": "k", "FRAPPE_API_SECRET": SECRET[:4] + "\n" + SECRET[4:]}
		with mock.patch.dict(os.environ, env, clear=True):
			with self.assertRaises(ts_common.SuiteError) as caught:
				ts_frappe.FrappeClient.from_env("https://erp.example.com")
		self.assertNotIn(SECRET[:4], str(caught.exception).replace("FRAPPE_API_SECRET", ""))
		self.assertIn("FRAPPE_API_SECRET", str(caught.exception))

	def test_a_transport_value_error_becomes_a_generic_suite_error(self):
		client, _ = client_with(ValueError(f'Invalid header value b"token k:{SECRET}\\n"'))
		with self.assertRaises(ts_common.SuiteError) as caught:
			client.logged_user()
		self.assertNotIn(SECRET, str(caught.exception))
		self.assertNotIn(SECRET, repr(caught.exception))
		self.assertIsNone(caught.exception.__cause__)


class ClassifyTests(unittest.TestCase):
	def test_error_table(self):
		rows = [
			("TimestampMismatchError", 417, "Document has been modified after you have opened it", "conflict"),
			("LinkExistsError", 417, "Cannot delete or cancel because TS-1 is linked with Salary Slip", "linked_docs"),
			("PermissionError", 403, "Not permitted", "permission"),
			(None, 403, "", "permission"),
			("DoesNotExistError", 404, "", "not_found"),
			(None, 401, "Invalid login credentials", "auth"),
			("ValidationError", 417, "Self approval is not allowed", "workflow_blocked"),
			("ValidationError", 417, "Not a valid Workflow Action", "workflow_blocked"),
			("WorkflowPermissionError", 417, "", "workflow_blocked"),
			("UpdateAfterSubmitError", 417, "", "immutable_submitted"),
			("ValidationError", 417, "Row 1: From Time is overlapping with TS-9", "overlap"),
			("ValidationError", 417, "Could not find Activity Type: Foo", "validation"),
			("MandatoryError", 417, "", "validation"),
			(None, 502, "Bad Gateway", "server"),
			(None, 418, "teapot", "error"),
		]
		for exc_type, status, message, expected in rows:
			with self.subTest(exc_type=exc_type, status=status, message=message):
				self.assertEqual(ts_frappe.classify(exc_type, status, message), expected)

	def test_specific_message_beats_the_generic_validation_exc_type(self):
		# Self approval arrives as a plain ValidationError (417) in Frappe v15.
		error = FrappeError("x", exc_type="ValidationError", status=417, detail="Self approval is not allowed")
		self.assertEqual(error.code, "workflow_blocked")

	def test_http_failure_carries_status_exc_type_and_code(self):
		failure = http_error(417, {"exc_type": "TimestampMismatchError", "_server_messages": json.dumps([json.dumps({"message": "stale"})])})
		client, _ = client_with(failure)
		with self.assertRaises(FrappeError) as caught:
			client.get_timesheet("TS-1")
		error = caught.exception
		self.assertEqual((error.status, error.exc_type, error.code), (417, "TimestampMismatchError", "conflict"))
		self.assertIsInstance(error, ts_common.SuiteError)

	def test_unreachable_server_is_status_none(self):
		client, _ = client_with(urllib.error.URLError("refused"))
		with self.assertRaises(FrappeError) as caught:
			client.logged_user()
		self.assertEqual((caught.exception.status, caught.exception.code), (None, "unreachable"))

	def test_error_text_never_contains_the_secret_even_if_the_server_echoes_it(self):
		with mock.patch.dict(os.environ, {"FRAPPE_API_SECRET": SECRET}):
			client, _ = client_with(http_error(401, {"exception": f"bad token k:{SECRET}"}))
			with self.assertRaises(FrappeError) as caught:
				client.logged_user()
		self.assertNotIn(SECRET, str(caught.exception))
		self.assertNotIn(SECRET, caught.exception.detail)
		self.assertEqual(caught.exception.code, "auth")


class WorkflowDetectionTests(unittest.TestCase):
	def test_workflow_comes_from_getdoctype_with_string_doc_status(self):
		client, opener = client_with(getdoctype(WORKFLOW_DOC))
		workflow = client.workflow_for("Timesheet")
		self.assertEqual([state["doc_status"] for state in workflow["states"]], ["0", "1", "2"])
		self.assertEqual(workflow["name"], "Timesheet Approval")
		self.assertIn("frappe.desk.form.load.getdoctype", opener.requests[0].full_url)
		self.assertNotIn("/api/resource/Workflow", opener.requests[0].full_url)

	def test_no_workflow_is_none_only_when_the_server_answered(self):
		client, _ = client_with(getdoctype())
		self.assertIsNone(client.workflow_for("Timesheet", {"name": "TS-1"}))

	def test_a_refused_or_failed_lookup_is_never_read_as_no_workflow(self):
		for failure in (http_error(403, {"exc_type": "PermissionError"}), http_error(500, "boom"), urllib.error.URLError("x")):
			with self.subTest(failure=failure):
				client, _ = client_with(failure)
				with self.assertRaises(FrappeError):
					client.workflow_for("Timesheet")

	def test_malformed_answer_fails_closed(self):
		client, _ = client_with({"message": "ok"})
		with self.assertRaises(FrappeError):
			client.workflow_for("Timesheet")

	def test_a_doc_in_a_workflow_state_contradicts_no_workflow(self):
		client, _ = client_with(getdoctype())
		with self.assertRaises(FrappeError) as caught:
			client.workflow_for("Timesheet", {"name": "TS-1", "workflow_state": "Pending"})
		self.assertEqual(caught.exception.code, "workflow_unknown")


class WriteCallTests(unittest.TestCase):
	def test_update_sends_modified_verbatim_and_requires_it(self):
		client, opener = client_with({"data": {"name": "TS-1"}})
		client.update_timesheet("TS-1", {"note": "x"}, "2026-09-08 10:00:00.123456")
		body = json.loads(opener.requests[0].data)
		self.assertEqual(body["modified"], "2026-09-08 10:00:00.123456")
		self.assertEqual(opener.requests[0].get_method(), "PUT")
		with self.assertRaises(ts_common.SuiteError):
			client.update_timesheet("TS-1", {"note": "x"}, "")
		self.assertEqual(len(opener.requests), 1)

	def test_submit_sends_the_full_doc_as_json_string(self):
		client, opener = client_with({"message": {"name": "TS-1", "docstatus": 1}})
		doc = {"name": "TS-1", "modified": "m", "time_logs": [{"hours": 1}]}
		client.submit_doc(doc)
		request = opener.requests[0]
		self.assertTrue(request.full_url.endswith("/api/method/frappe.client.submit"))
		self.assertEqual(json.loads(json.loads(request.data)["doc"]), doc)

	def test_delete_uses_delete_and_a_missing_doc_is_not_found(self):
		client, opener = client_with({"message": "ok"}, http_error(404, {"exc_type": "DoesNotExistError"}))
		client.delete_timesheet("TS 1/x")
		self.assertEqual(opener.requests[0].get_method(), "DELETE")
		self.assertTrue(opener.requests[0].full_url.endswith("/api/resource/Timesheet/TS%201%2Fx"))
		with self.assertRaises(FrappeError) as caught:
			client.delete_timesheet("TS-9")
		self.assertEqual((caught.exception.status, caught.exception.code), (404, "not_found"))

	def test_has_permission_is_true_only_for_an_explicit_true(self):
		client, opener = client_with(
			{"message": {"has_permission": True}}, {"message": {"has_permission": False}}, {"message": None}
		)
		self.assertTrue(client.has_permission("Timesheet", "TS-1", "submit"))
		self.assertFalse(client.has_permission("Timesheet", "TS-1", "cancel"))
		with self.assertRaises(FrappeError):
			client.has_permission("Timesheet", "TS-1", "delete")
		self.assertIn("perm_type=submit", opener.requests[0].full_url)


class FakeClientTests(unittest.TestCase):
	def sheet(self, **extra):
		return {"name": "TS-1", "docstatus": 0, "employee": "HR-EMP-00001", "time_logs": [], **extra}

	def test_stale_modified_is_a_conflict_and_writes_nothing(self):
		fake = FakeClient(existing=[self.sheet()])
		seen = fake.get_timesheet("TS-1")["modified"]
		fake.bump_modified("TS-1")
		with self.assertRaises(FrappeError) as caught:
			fake.update_timesheet("TS-1", {"note": "mine"}, seen)
		self.assertEqual(caught.exception.code, "conflict")
		self.assertNotIn("note", fake.docs["TS-1"])

	def test_writes_fill_costing_fields_so_a_naive_equality_diff_fails(self):
		fake = FakeClient(existing=[self.sheet()])
		modified = fake.get_timesheet("TS-1")["modified"]
		row = {"activity_type": "Coding", "hours": 2.0, "costing_amount": 0, "costing_rate": 0}
		fake.update_timesheet("TS-1", {"time_logs": [row]}, modified)
		stored_row = fake.get_timesheet("TS-1")["time_logs"][0]
		self.assertNotEqual(stored_row["costing_amount"], row["costing_amount"])
		self.assertNotEqual(fake.get_timesheet("TS-1")["modified"], modified)

	def test_submit_needs_the_current_modified_and_the_full_doc(self):
		fake = FakeClient(existing=[self.sheet(time_logs=[{"hours": 1.0}])])
		doc = fake.get_timesheet("TS-1")
		fake.bump_modified("TS-1")
		with self.assertRaises(FrappeError):
			fake.submit_doc(doc)
		self.assertEqual(fake.docs["TS-1"]["docstatus"], 0)
		fake.submit_doc(fake.get_timesheet("TS-1"))
		self.assertEqual(fake.docs["TS-1"]["docstatus"], 1)
		with self.assertRaises(FrappeError) as caught:
			fake.update_timesheet("TS-1", {"note": "x"}, None)
		self.assertEqual(caught.exception.code, "immutable_submitted")

	def test_permissions_and_linked_docs_gate_cancel_and_delete(self):
		fake = FakeClient(existing=[self.sheet(), self.sheet(name="TS-2", docstatus=1)], deny={"delete"}, linked={"TS-2": "Salary Slip SAL-9"})
		self.assertFalse(fake.has_permission("Timesheet", "TS-1", "delete"))
		self.assertTrue(fake.has_permission("Timesheet", "TS-1", "submit"))
		with self.assertRaises(FrappeError) as denied:
			fake.delete_timesheet("TS-1")
		self.assertEqual(denied.exception.code, "permission")
		with self.assertRaises(FrappeError) as linked:
			fake.cancel_timesheet("TS-2")
		self.assertEqual(linked.exception.code, "linked_docs")
		self.assertEqual(fake.docs["TS-2"]["docstatus"], 1)

	def test_inject_is_one_shot_and_reads_and_writes_are_split(self):
		fake = FakeClient(existing=[self.sheet()])
		fake.inject("cancel", FrappeError("boom", status=500))
		with self.assertRaises(FrappeError):
			fake.cancel_timesheet("TS-1")
		fake.get_timesheet("TS-1")
		fake.list_docs("Timesheet", [], ["name"])
		self.assertEqual(fake.writes(), ["cancel"])
		self.assertEqual(fake.reads(), ["get", "list_docs"])

	def test_list_docs_sees_timesheets_written_through_the_client(self):
		fake = FakeClient(existing=[self.sheet(docstatus=2)], records={"Project": [{"name": "P1", "status": "Open"}]})
		created = fake.create_timesheet({"employee": "HR-EMP-00001", "amended_from": "TS-1", "time_logs": []})
		self.assertEqual(created["name"], "TS-1-1")
		found = fake.list_docs("Timesheet", [["amended_from", "=", "TS-1"], ["docstatus", "<", 2]], ["name"])
		self.assertEqual(found, [{"name": "TS-1-1"}])
		self.assertEqual(fake.list_docs("Project", [["status", "=", "Open"]], ["name"]), [{"name": "P1"}])

	def test_workflow_detection_in_the_fake_matches_the_client_contract(self):
		fake = FakeClient(existing=[self.sheet()], workflow={"name": "W", "states": [{"state": "Approved", "doc_status": "1"}]})
		self.assertEqual(fake.workflow_for("Timesheet")["states"][0]["doc_status"], "1")
		self.assertIsNone(FakeClient().workflow_for("Timesheet"))


if __name__ == "__main__":
	unittest.main()
