"""Unit tests for ts_lifecycle.py (sync, update, amend, cancel, submit, pull). Run from the skill folder:

    python3 -m unittest discover -s scripts -p 'test_ts_lifecycle*.py'
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import stat
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import timesheet_suite as ts  # noqa: E402  (build_timesheet only)
import ts_common  # noqa: E402
import ts_lifecycle as lc  # noqa: E402
from ts_common import Env  # noqa: E402
from ts_fakes import FakeClient  # noqa: E402
from ts_frappe import FrappeError  # noqa: E402
from ts_testkit import ACTIVITY_TYPES, PROFILE, PROJECTS, TempHome, entry, silent, spec  # noqa: E402

SITE = "https://erp.example.com"
EMPLOYEE = "HR-EMP-00001"
TOKEN = f"{EMPLOYEE}/2026-09-08"
CATALOGUE = {"Activity Type": [{"name": "Coding"}, {"name": "Review"}], "Project": [{"name": "PROJ-0019"}]}


def build(*hours):
	doc, _ = ts.build_timesheet(spec([entry(hours=h) for h in hours or (2,)]), PROFILE, ACTIVITY_TYPES, PROJECTS)
	return doc


def client_with(*sheets, **kwargs):
	"""A FakeClient whose stubs belong to the profile employee and whose catalogue knows Coding/Review/PROJ-0019."""
	stubs = [{"employee": EMPLOYEE, **sheet} for sheet in sheets]
	kwargs.setdefault("records", CATALOGUE)
	return FakeClient(existing=stubs, **kwargs)


def modified(client, name):
	return client.docs[name]["modified"]


def mutations(client):
	return [call for call in client.calls if call[0] in set(client.writes())]


class PlanTests(unittest.TestCase):
	@staticmethod
	def sheet(name, docstatus, modified="2026-09-08 10:00:00"):
		return {"name": name, "docstatus": docstatus, "modified": modified}

	def test_plan_for_each_docstatus(self):
		cases = [
			([], {"action": "create", "target": None}),
			([self.sheet("TS-1", 0)], {"action": "update", "target": "TS-1"}),
			([self.sheet("TS-1", 1)], {"action": "cancel_and_amend", "target": "TS-1"}),
			(
				[self.sheet("TS-1", 2, "2026-09-08 09:00:00"), self.sheet("TS-1-1", 2, "2026-09-08 11:00:00")],
				{"action": "amend_cancelled", "target": "TS-1-1"},
			),
			([self.sheet("TS-2", 2), self.sheet("TS-3", 0)], {"action": "update", "target": "TS-3"}),
		]
		for existing, expected in cases:
			with self.subTest(existing=existing):
				self.assertEqual(lc.plan_sync(existing), expected)

	def test_two_active_timesheets_are_ambiguous(self):
		plan = lc.plan_sync([self.sheet("TS-1", 0), self.sheet("TS-2", 1)])
		self.assertEqual(plan, {"action": "ambiguous", "candidates": ["TS-1", "TS-2"]})


class WritePayloadTests(unittest.TestCase):
	def test_create_never_sends_naming_series_or_server_fields(self):
		doc = {**build(), "name": "TS-1", "status": "Submitted", "modified": "x", "amended_from": "old"}
		doc["time_logs"][0].update(name="row1", parent="TS-1", parenttype="Timesheet", parentfield="time_logs")
		payload = lc.write_payload(doc)
		for key in ("naming_series", "name", "status", "modified", "amended_from"):
			self.assertNotIn(key, payload)
		self.assertEqual((payload["doctype"], payload["docstatus"]), ("Timesheet", 0))
		for key in ("name", "parent", "parenttype", "parentfield"):
			self.assertNotIn(key, payload["time_logs"][0])

	def test_amended_from_is_set_only_when_asked(self):
		self.assertEqual(lc.write_payload(build(), amended_from="TS-1")["amended_from"], "TS-1")
		self.assertNotIn("amended_from", lc.write_payload(build()))


class SyncTests(unittest.TestCase):
	"""Migrated from the legacy SyncTests: same outcomes, new confirm flags (`--apply` is gone)."""

	def setUp(self):
		self.doc = build(2)

	def sync(self, client, **kwargs):
		return lc.run_sync(client, self.doc, site=SITE, out=silent, **kwargs)

	def test_dry_run_writes_nothing(self):
		client = client_with({"name": "TS-1", "docstatus": 1})
		plan = self.sync(client)
		self.assertEqual((plan["action"], plan["applied"]), ("cancel_and_amend", False))
		self.assertEqual(client.writes(), [])

	def test_identity_mismatch_stops_before_writing(self):
		client = FakeClient(employees=[{"name": "HR-EMP-09999", "employee_name": "Someone Else"}])
		with self.assertRaisesRegex(ts_common.SuiteError, "not HR-EMP-00001"):
			self.sync(client, confirm_create=TOKEN)
		self.assertEqual(client.writes(), [])

	def test_creates_a_draft_when_nothing_exists(self):
		client = FakeClient()
		result = self.sync(client, confirm_create=TOKEN)
		self.assertEqual(client.writes(), ["create"])
		payload = client.calls[[c[0] for c in client.calls].index("create")][1]
		self.assertEqual((payload["docstatus"], payload["doctype"]), (0, "Timesheet"))
		self.assertNotIn("naming_series", payload)
		self.assertEqual(result["url"], "https://erp.example.com/app/timesheet/TS-NEW")

	def test_attendance_rejection_is_explained_and_writes_nothing_more(self):
		client = FakeClient()
		client.inject(
			"create",
			FrappeError(
				"Field weekly_off_based_on does not exist on HR Settings; Timesheet for 18-10-2026 cannot be created "
				"because attendance is not marked Present.",
				status=417,
			),
		)
		with self.assertRaises(lc.LifecycleError) as caught:
			self.sync(client, confirm_create=TOKEN)
		self.assertEqual(caught.exception.code, "attendance")
		self.assertIn("Ask HR", str(caught.exception))
		self.assertNotIn("weekly_off_based_on does not exist on HR Settings;", str(caught.exception))
		self.assertEqual(client.writes(), ["create"])

	def test_updates_a_draft_by_replacing_its_rows(self):
		client = client_with({"name": "TS-1", "docstatus": 0})
		self.sync(client, confirm_update="TS-1", expect_modified=modified(client, "TS-1"))
		self.assertEqual(client.writes(), ["update"])
		_, name, payload = mutations(client)[0]
		self.assertEqual(name, "TS-1")
		self.assertNotIn("doctype", payload)
		self.assertNotIn("docstatus", payload)
		self.assertEqual(len(payload["time_logs"]), 1)

	def test_ambiguous_stops_even_on_a_dry_run(self):
		client = client_with({"name": "TS-1", "docstatus": 0}, {"name": "TS-2", "docstatus": 0})
		with self.assertRaisesRegex(ts_common.SuiteError, "Several"):
			self.sync(client)

	def test_non_draft_input_is_refused(self):
		with self.assertRaisesRegex(ts_common.SuiteError, "draft"):
			lc.run_sync(FakeClient(), {**self.doc, "docstatus": 1}, site="x", out=silent)

	def test_sync_never_cancels_a_submitted_sheet_and_says_use_amend(self):
		client = client_with({"name": "TS-1", "docstatus": 1})
		result = self.sync(client)
		self.assertEqual((result["status"], result["applied"]), ("use_amend", False))
		self.assertIn("amend TS-1", result["needs"])
		with self.assertRaises(lc.ConfirmationRequired):
			self.sync(client, confirm_update="TS-1", expect_modified=modified(client, "TS-1"))
		self.assertEqual(client.writes(), [])


class AmendTests(unittest.TestCase):
	"""The legacy sync-driven cancel/amend/workflow-cancel tests, now `amend` tests with the same assertions."""

	def setUp(self):
		self.doc = build(2)

	def amend(self, client, name="TS-1", **kwargs):
		return lc.run_amend(client, name, self.doc, site=SITE, out=silent, **kwargs)

	def test_submitted_needs_explicit_confirmation_of_that_timesheet(self):
		client = client_with({"name": "TS-1", "docstatus": 1})
		with self.assertRaisesRegex(ts_common.SuiteError, "--confirm-cancel TS-1"):
			self.amend(client, confirm_cancel="TS-OTHER", expect_modified=modified(client, "TS-1"))
		self.assertEqual(client.writes(), [])

	def test_submitted_is_cancelled_then_amended(self):
		client = client_with({"name": "TS-1", "docstatus": 1})
		result = self.amend(client, confirm_cancel="TS-1", expect_modified=modified(client, "TS-1"))
		self.assertEqual(client.writes(), ["cancel", "create"])
		self.assertEqual(mutations(client)[1][1]["amended_from"], "TS-1")
		self.assertEqual((result["created"], result["name"]), ("TS-1-1", "TS-1-1"))
		self.assertEqual(result["steps_done"], ["cancel", "create"])

	def test_workflow_cancel_is_used_when_direct_cancel_is_refused(self):
		client = client_with(
			{"name": "TS-1", "docstatus": 1},
			cancel_error="Not allowed",
			transitions=[
				{"action": "Approve", "next_state": "Approved"},
				{"action": "Cancel", "next_state": "Cancelled"},
			],
			cancel_states={"Cancelled"},
		)
		self.amend(client, confirm_cancel="TS-1", expect_modified=modified(client, "TS-1"))
		self.assertEqual(client.writes(), ["cancel", "workflow", "create"])
		self.assertEqual(mutations(client)[1], ("workflow", "TS-1", "Cancel"))

	def test_stops_when_no_cancel_path_exists(self):
		client = client_with(
			{"name": "TS-1", "docstatus": 1},
			cancel_error="Not allowed",
			transitions=[{"action": "Approve", "next_state": "Approved"}],
			cancel_states={"Cancelled"},
		)
		with self.assertRaisesRegex(ts_common.SuiteError, "approver"):
			self.amend(client, confirm_cancel="TS-1", expect_modified=modified(client, "TS-1"))
		self.assertEqual(client.writes(), ["cancel"])

	def test_only_cancelled_is_amended_into_a_new_draft(self):
		client = client_with({"name": "TS-1", "docstatus": 2})
		self.amend(client, confirm_create="TS-1", expect_modified=modified(client, "TS-1"))
		self.assertEqual(client.writes(), ["create"])
		self.assertEqual(mutations(client)[0][1]["amended_from"], "TS-1")

	def test_amend_of_a_draft_is_refused_in_favour_of_update(self):
		client = client_with({"name": "TS-1", "docstatus": 0})
		with self.assertRaisesRegex(ts_common.SuiteError, "use `update"):
			self.amend(client)

	def test_amend_aborts_before_cancel_when_a_name_does_not_exist(self):
		client = client_with({"name": "TS-1", "docstatus": 1}, records={"Activity Type": [], "Project": CATALOGUE["Project"]})
		with self.assertRaisesRegex(ts_common.SuiteError, "Activity Type 'Coding'"):
			self.amend(client, confirm_cancel="TS-1", expect_modified=modified(client, "TS-1"))
		self.assertEqual(client.writes(), [])

	def test_amend_aborts_before_cancel_on_overlap_with_another_sheet(self):
		other = {**build(1), "name": "TS-9", "docstatus": 1, "employee": EMPLOYEE}
		client = client_with({"name": "TS-1", "docstatus": 1})
		client.docs["TS-9"] = {**other, "modified": "2026-09-08 08:00:00.000000"}
		with self.assertRaisesRegex(ts_common.SuiteError, "TS-9"):
			self.amend(client, confirm_cancel="TS-1", expect_modified=modified(client, "TS-1"))
		self.assertEqual(client.writes(), [])

	def test_partial_failure_reports_steps_done_and_a_retry_creates_only(self):
		client = client_with({"name": "TS-1", "docstatus": 1})
		client.inject("create", FrappeError("Could not find Project X", exc_type="ValidationError", status=417))
		with self.assertRaises(lc.LifecycleError) as caught:
			self.amend(client, confirm_cancel="TS-1", expect_modified=modified(client, "TS-1"))
		self.assertEqual(caught.exception.steps_done, ["cancel"])
		self.assertIn("re-run", str(caught.exception))
		client.calls.clear()
		result = self.amend(client, confirm_create="TS-1", expect_modified=modified(client, "TS-1"))
		self.assertEqual(client.writes(), ["create"])
		self.assertEqual(result["steps_done"], ["create"])

	def test_amend_keeps_the_cancel_in_steps_done_when_verification_fails(self):
		client = client_with({"name": "TS-1", "docstatus": 1})
		seen = modified(client, "TS-1")
		real = client.get_timesheet

		def flaky(name):
			if ("cancel", name) in client.calls:
				raise FrappeError("Could not reach the site", code="unreachable")
			return real(name)

		client.get_timesheet = flaky
		with self.assertRaises(lc.LifecycleError) as caught:
			self.amend(client, confirm_cancel="TS-1", expect_modified=seen)
		self.assertEqual(caught.exception.steps_done, ["cancel"])
		self.assertEqual(client.writes(), ["cancel"])

	def test_amend_twice_is_refused_as_a_duplicate(self):
		client = client_with({"name": "TS-1", "docstatus": 2}, {"name": "TS-1-1", "docstatus": 0, "amended_from": "TS-1"})
		with self.assertRaises(lc.LifecycleError) as caught:
			self.amend(client, confirm_create="TS-1", expect_modified=modified(client, "TS-1"))
		self.assertEqual(caught.exception.code, "duplicate_amendment")
		self.assertEqual(client.writes(), [])

	def test_amend_of_a_cancelled_chain_amends_the_leaf(self):
		client = client_with(
			{"name": "TS-1", "docstatus": 2},
			{"name": "TS-1-1", "docstatus": 2, "amended_from": "TS-1"},
		)
		dry = self.amend(client)
		self.assertEqual((dry["confirm_token"], dry["modified"]), ("TS-1", modified(client, "TS-1-1")))
		self.amend(client, confirm_create="TS-1", expect_modified=dry["modified"])
		self.assertEqual(mutations(client)[0][1]["amended_from"], "TS-1-1")

	def test_file_for_another_employee_is_refused(self):
		client = client_with({"name": "TS-1", "docstatus": 1, "employee": "HR-EMP-00002"})
		with self.assertRaisesRegex(ts_common.SuiteError, "belongs to HR-EMP-00002"):
			self.amend(client)


class GateTests(unittest.TestCase):
	def test_no_flag_means_no_writes_on_any_command(self):
		doc = build(2)
		workflow_free = lambda **kw: client_with(  # noqa: E731
			{"name": "TS-1", "docstatus": 0, "employee": EMPLOYEE, "time_logs": doc["time_logs"], "total_hours": 2}, **kw
		)
		submitted = lambda: client_with({"name": "TS-1", "docstatus": 1})  # noqa: E731
		cases = {
			"sync": lambda c: lc.run_sync(c, doc, site=SITE, out=silent),
			"update": lambda c: lc.run_update(c, "TS-1", build(3), site=SITE, out=silent),
			"amend": lambda c: lc.run_amend(c, "TS-1", doc, site=SITE, out=silent),
			"cancel": lambda c: lc.run_cancel(c, "TS-1", site=SITE, out=silent),
			"submit": lambda c: lc.run_submit(c, "TS-1", site=SITE, out=silent),
		}
		for name, run in cases.items():
			client = submitted() if name == "amend" else workflow_free()
			if name == "cancel":
				client = submitted()
			with self.subTest(command=name):
				result = run(client)
				self.assertFalse(result["applied"])
				self.assertEqual(client.writes(), [])
				self.assertTrue(result["confirm_token"])

	def test_wrong_token_is_an_error_not_a_dry_run(self):
		client = client_with({"name": "TS-1", "docstatus": 1})
		for given in ("ts-1", "TS-1 ", "TS-2", ""):
			with self.subTest(token=given), self.assertRaises(lc.ConfirmationRequired) as caught:
				lc.run_cancel(client, "TS-1", site=SITE, confirm_cancel=given, expect_modified=modified(client, "TS-1"), out=silent)
			self.assertEqual(caught.exception.exit_code, 2)
		self.assertEqual(client.writes(), [])

	def test_confirm_flags_are_not_interchangeable(self):
		draft = client_with({"name": "TS-1", "docstatus": 0})
		with self.assertRaises(lc.ConfirmationRequired):
			lc.run_cancel(draft, "TS-1", site=SITE, confirm_cancel="TS-1", expect_modified=modified(draft, "TS-1"), out=silent)
		submitted = client_with({"name": "TS-1", "docstatus": 1})
		with self.assertRaises(lc.ConfirmationRequired):
			lc.run_cancel(submitted, "TS-1", site=SITE, confirm_delete="TS-1", expect_modified=modified(submitted, "TS-1"), out=silent)
		with self.assertRaises(lc.ConfirmationRequired):  # an update approval cannot authorise a cancel+amend
			lc.run_amend(submitted, "TS-1", build(2), site=SITE, confirm_create="TS-1", expect_modified=modified(submitted, "TS-1"), out=silent)
		self.assertEqual(draft.writes() + submitted.writes(), [])

	def test_confirm_without_expect_modified_is_confirmation_required(self):
		client = client_with({"name": "TS-1", "docstatus": 1})
		with self.assertRaisesRegex(lc.ConfirmationRequired, "expect-modified"):
			lc.run_cancel(client, "TS-1", site=SITE, confirm_cancel="TS-1", out=silent)
		self.assertEqual(client.writes(), [])

	def test_stale_expect_modified_writes_nothing(self):
		client = client_with({"name": "TS-1", "docstatus": 1})
		stale = modified(client, "TS-1")
		client.bump_modified("TS-1")
		with self.assertRaises(lc.ConfirmationRequired) as caught:
			lc.run_cancel(client, "TS-1", site=SITE, confirm_cancel="TS-1", expect_modified=stale, out=silent)
		self.assertEqual(caught.exception.code, "conflict")
		self.assertEqual(client.writes(), [])

	def test_race_after_the_dry_run_is_caught_by_the_server_timestamp(self):
		client = client_with({"name": "TS-1", "docstatus": 0})
		seen = modified(client, "TS-1")
		real = client.get_timesheet

		def racing(name):  # the approver edits between our read and our write
			doc = real(name)
			client.bump_modified(name)
			return doc

		client.get_timesheet = racing
		with self.assertRaises(FrappeError) as caught:
			lc.run_update(client, "TS-1", build(4), site=SITE, confirm_update="TS-1", expect_modified=seen, out=silent)
		self.assertEqual(caught.exception.code, "conflict")

	def test_approvals_are_never_read_from_the_environment_or_profile(self):
		client = client_with({"name": "TS-1", "docstatus": 0, "total_hours": 2, "time_logs": build(2)["time_logs"]})
		env = {"TIMESHEET_CONFIRM_SUBMIT": "TS-1", "CONFIRM_SUBMIT": "TS-1", "TIMESHEET_APPLY": "1"}
		with mock.patch.dict(os.environ, env):
			result = lc.run_submit(client, "TS-1", site=SITE, out=silent)
		self.assertFalse(result["applied"])
		self.assertEqual(client.writes(), [])


class CancelTests(unittest.TestCase):
	def test_submitted_cancel_direct(self):
		client = client_with({"name": "TS-1", "docstatus": 1})
		result = lc.run_cancel(client, "TS-1", site=SITE, confirm_cancel="TS-1", expect_modified=modified(client, "TS-1"), out=silent)
		self.assertEqual((client.writes(), result["docstatus_after"]), (["cancel"], 2))

	def test_draft_cancel_is_a_delete_with_its_own_flag(self):
		client = client_with({"name": "TS-1", "docstatus": 0})
		dry = lc.run_cancel(client, "TS-1", site=SITE, out=silent)
		self.assertEqual((dry["plan"], dry["confirm_flag"]), (["delete"], "confirm-delete"))
		lc.run_cancel(client, "TS-1", site=SITE, confirm_delete="TS-1", expect_modified=dry["modified"], out=silent)
		self.assertEqual(client.writes(), ["delete"])
		self.assertNotIn("TS-1", client.docs)

	def test_delete_of_an_already_deleted_draft_is_success(self):
		client = client_with({"name": "TS-1", "docstatus": 0})
		seen = modified(client, "TS-1")
		real_delete = client.delete_timesheet

		def delete(name):  # someone else removed it between our read and our call
			real_delete(name)
			raise FrappeError("gone", exc_type="DoesNotExistError", status=404)

		client.delete_timesheet = delete
		result = lc.run_cancel(client, "TS-1", site=SITE, confirm_delete="TS-1", expect_modified=seen, out=silent)
		self.assertEqual(result["status"], "applied")
		client = client_with({"name": "TS-2", "docstatus": 0})
		client.inject("delete", FrappeError("boom", status=500))
		with self.assertRaises(FrappeError):
			lc.run_cancel(client, "TS-2", site=SITE, confirm_delete="TS-2", expect_modified=modified(client, "TS-2"), out=silent)

	def test_delete_rereads_modified_right_before_deleting(self):
		client = client_with({"name": "TS-1", "docstatus": 0})
		seen = modified(client, "TS-1")
		real = client.has_permission

		def bumping(doctype, name, ptype):  # an approver touches the draft after our first read
			client.bump_modified(name)
			return real(doctype, name, ptype)

		client.has_permission = bumping
		with self.assertRaises(lc.LifecycleError) as caught:
			lc.run_cancel(client, "TS-1", site=SITE, confirm_delete="TS-1", expect_modified=seen, out=silent)
		self.assertEqual(caught.exception.code, "conflict")
		self.assertEqual(client.writes(), [])
		self.assertIn("TS-1", client.docs)

	def test_cancel_succeeded_but_verification_failed_still_reports_the_cancel(self):
		client = client_with({"name": "TS-1", "docstatus": 1})
		seen = modified(client, "TS-1")
		real = client.get_timesheet

		def flaky(name):
			if ("cancel", name) in client.calls:
				raise FrappeError("Could not reach the site", code="unreachable")
			return real(name)

		client.get_timesheet = flaky
		lines = []
		with self.assertRaises(lc.LifecycleError) as caught:
			lc.run_cancel(client, "TS-1", site=SITE, confirm_cancel="TS-1", expect_modified=seen, out=silent, audit=lambda **f: lines.append(f))
		self.assertEqual(caught.exception.steps_done, ["cancel"])
		self.assertEqual((lines[0]["status"], lines[0]["steps_done"]), ("partial", ["cancel"]))

	def test_already_cancelled_is_a_no_op(self):
		client = client_with({"name": "TS-1", "docstatus": 2})
		result = lc.run_cancel(client, "TS-1", site=SITE, out=silent)
		self.assertEqual((result["status"], client.writes()), ("already_cancelled", []))

	def test_linked_documents_block_the_cancel_and_change_nothing(self):
		client = client_with({"name": "TS-1", "docstatus": 1}, linked={"TS-1": "Salary Slip SAL-9"})
		with self.assertRaises(FrappeError) as caught:
			lc.run_cancel(client, "TS-1", site=SITE, confirm_cancel="TS-1", expect_modified=modified(client, "TS-1"), out=silent)
		self.assertEqual(caught.exception.code, "linked_docs")
		self.assertEqual(client.docs["TS-1"]["docstatus"], 1)

	def test_role_without_permission_is_told_in_the_dry_run(self):
		client = client_with({"name": "TS-1", "docstatus": 1}, deny={"cancel"})
		with self.assertRaises(lc.LifecycleError) as caught:
			lc.run_cancel(client, "TS-1", site=SITE, out=silent)
		self.assertEqual(caught.exception.code, "permission")
		self.assertEqual(client.writes(), [])


class SubmitTests(unittest.TestCase):
	def sheet(self, **extra):
		return {"name": "TS-1", "docstatus": 0, "total_hours": 2.0, "time_logs": build(2)["time_logs"], **extra}

	def submit(self, client, **kwargs):
		kwargs.setdefault("expect_modified", modified(client, "TS-1"))
		return lc.run_submit(client, "TS-1", site=SITE, confirm_submit="TS-1", out=silent, **kwargs)

	def test_plain_submit_when_the_site_has_no_workflow(self):
		client = client_with(self.sheet())
		result = self.submit(client)
		self.assertEqual((client.writes(), result["submitted"], result["docstatus"]), (["submit"], True, 1))

	def test_workflow_site_applies_the_single_submitting_action_and_never_plain_submits(self):
		workflow = {"name": "W", "states": [
			{"state": "Draft", "doc_status": "0"}, {"state": "Approved", "doc_status": "1"}, {"state": "Rejected", "doc_status": "2"}]}
		transitions = [{"action": "Reject", "next_state": "Rejected"}, {"action": "Approve", "next_state": "Approved"}]
		client = client_with(self.sheet(workflow_state="Draft"), workflow=workflow, transitions=transitions)
		dry = lc.run_submit(client, "TS-1", site=SITE, out=silent)
		self.assertEqual(dry["action"], "Approve")  # Reject leads to docstatus 2: never offered
		result = self.submit(client, action="Approve")
		self.assertEqual(client.writes(), ["workflow"])
		self.assertEqual((result["submitted"], result["docstatus"]), (True, 1))

	def test_dry_run_prints_the_full_confirm_command_including_the_action(self):
		workflow = {"name": "W", "states": [{"state": "Draft", "doc_status": "0"}, {"state": "Approved", "doc_status": "1"}]}
		client = client_with(self.sheet(workflow_state="Draft"), workflow=workflow, transitions=[{"action": "Approve", "next_state": "Approved"}])
		lines = []
		result = lc.run_submit(client, "TS-1", site=SITE, out=lines.append)
		for text in (result["needs"], lines[-1]):
			self.assertIn("--confirm-submit TS-1", text)
			self.assertIn("--expect-modified", text)
			self.assertIn("--action 'Approve'", text)

	def test_confirm_run_must_repeat_the_echoed_action(self):
		workflow = {"name": "W", "states": [{"state": "Draft", "doc_status": "0"}, {"state": "Pending", "doc_status": "0"}]}
		client = client_with(self.sheet(workflow_state="Draft"), workflow=workflow, transitions=[{"action": "Send", "next_state": "Pending"}])
		with self.assertRaises(lc.ConfirmationRequired):
			self.submit(client)  # no --action on the confirm run
		self.assertEqual(client.writes(), [])

	def test_pending_approval_is_a_normal_result(self):
		workflow = {"name": "W", "states": [{"state": "Draft", "doc_status": "0"}, {"state": "Pending", "doc_status": "0"}]}
		client = client_with(self.sheet(workflow_state="Draft"), workflow=workflow, transitions=[{"action": "Send", "next_state": "Pending"}])
		result = self.submit(client, action="Send")
		self.assertEqual((result["status"], result["submitted"], result["applied"]), ("pending_approval", False, True))
		self.assertEqual(result["workflow_state"], "Pending")

	def test_no_submitting_action_available_is_workflow_blocked(self):
		workflow = {"name": "W", "states": [{"state": "Draft", "doc_status": "0"}, {"state": "Rejected", "doc_status": "2"}]}
		client = client_with(self.sheet(workflow_state="Draft"), workflow=workflow, transitions=[{"action": "Reject", "next_state": "Rejected"}])
		with self.assertRaises(lc.LifecycleError) as caught:
			lc.run_submit(client, "TS-1", site=SITE, out=silent)
		self.assertEqual(caught.exception.code, "workflow_blocked")
		self.assertEqual(client.writes(), [])

	def test_unknown_workflow_detection_fails_closed(self):
		client = client_with(self.sheet(workflow_state="Draft"))  # state present, detection says none
		with self.assertRaises(FrappeError):
			lc.run_submit(client, "TS-1", site=SITE, out=silent)
		client = client_with(self.sheet())
		client.inject("workflow_for", FrappeError("Not permitted", exc_type="PermissionError", status=403))
		with self.assertRaises(FrappeError):
			lc.run_submit(client, "TS-1", site=SITE, out=silent)
		self.assertEqual(client.writes(), [])

	def test_race_between_dry_run_and_workflow_apply_is_a_conflict(self):
		workflow = {"name": "W", "states": [{"state": "Draft", "doc_status": "0"}, {"state": "Approved", "doc_status": "1"}]}
		client = client_with(self.sheet(workflow_state="Draft"), workflow=workflow, transitions=[{"action": "Approve", "next_state": "Approved"}])
		seen = modified(client, "TS-1")
		client.bump_modified("TS-1")
		with self.assertRaises(lc.ConfirmationRequired):
			self.submit(client, action="Approve", expect_modified=seen)
		self.assertEqual(client.writes(), [])

	def test_already_submitted_and_cancelled_and_empty(self):
		done = client_with({"name": "TS-1", "docstatus": 1})
		self.assertEqual(lc.run_submit(done, "TS-1", site=SITE, out=silent)["status"], "already_submitted")
		dead = client_with({"name": "TS-1", "docstatus": 2})
		with self.assertRaisesRegex(ts_common.SuiteError, "amend"):
			lc.run_submit(dead, "TS-1", site=SITE, out=silent)
		empty = client_with({"name": "TS-1", "docstatus": 0})
		with self.assertRaisesRegex(ts_common.SuiteError, "no hours"):
			lc.run_submit(empty, "TS-1", site=SITE, out=silent)
		self.assertEqual(done.writes() + dead.writes() + empty.writes(), [])

	def test_server_ok_but_state_unchanged_is_reported(self):
		client = client_with(self.sheet())
		client.submit_doc = lambda doc: doc  # accepts, changes nothing
		with self.assertRaises(lc.LifecycleError) as caught:
			self.submit(client)
		self.assertEqual(caught.exception.code, "unexpected_state")


class UpdateTests(unittest.TestCase):
	def test_identical_content_is_a_noop_even_though_the_server_fills_costing_fields(self):
		client = client_with()
		doc = build(2)
		lc.run_sync(client, doc, site=SITE, confirm_create=TOKEN, out=silent)
		client.calls.clear()
		result = lc.run_update(client, "TS-NEW", doc, site=SITE, confirm_update="TS-NEW", expect_modified=modified(client, "TS-NEW"), out=silent)
		self.assertEqual((result["status"], client.writes()), ("noop", []))

	def test_identical_update_still_validates_the_confirmation_it_was_given(self):
		client = client_with()
		doc = build(2)
		lc.run_sync(client, doc, site=SITE, confirm_create=TOKEN, out=silent)
		seen = modified(client, "TS-NEW")
		with self.assertRaises(lc.ConfirmationRequired):
			lc.run_update(client, "TS-NEW", doc, site=SITE, confirm_update="WRONG", expect_modified=seen, out=silent)
		with self.assertRaises(lc.ConfirmationRequired):
			lc.run_update(client, "TS-NEW", doc, site=SITE, confirm_update="TS-NEW", out=silent)
		self.assertEqual(client.writes(), ["create"])

	def test_a_changed_row_is_diffed_and_written_with_the_read_modified(self):
		client = client_with()
		lc.run_sync(client, build(2), site=SITE, confirm_create=TOKEN, out=silent)
		client.calls.clear()
		dry = lc.run_update(client, "TS-NEW", build(1.5), site=SITE, out=silent)
		self.assertEqual(dry["diff"]["rows"]["changed"][0]["hours"], [2.0, 1.5])
		self.assertFalse(dry["applied"])
		result = lc.run_update(client, "TS-NEW", build(1.5), site=SITE, confirm_update="TS-NEW", expect_modified=dry["modified"], out=silent)
		self.assertEqual((client.writes(), result["total_hours"]), (["update"], 1.5))

	def test_update_refuses_submitted_documents_in_favour_of_amend(self):
		client = client_with({"name": "TS-1", "docstatus": 1})
		with self.assertRaisesRegex(ts_common.SuiteError, "amend TS-1"):
			lc.run_update(client, "TS-1", build(2), site=SITE, out=silent)

	def test_employee_mismatch_between_file_and_remote_is_refused(self):
		client = client_with({"name": "TS-1", "docstatus": 0, "employee": "HR-EMP-00002"})
		with self.assertRaisesRegex(ts_common.SuiteError, "HR-EMP-00002"):
			lc.run_update(client, "TS-1", build(2), site=SITE, out=silent)

	def test_diff_compares_only_the_explicit_field_set(self):
		noisy = {**build(2), "name": "TS-1", "note": "<div><p>A day of work. Total hours logged: 2h.</p></div>", "owner": "x"}
		noisy["time_logs"][0]["costing_amount"] = 999
		remote = lc.normalise_remote(noisy)
		self.assertTrue(lc.diff_docs(remote, build(2))["empty"])
		self.assertNotIn("owner", remote)
		self.assertNotIn("costing_amount", remote["time_logs"][0])


class PullTests(unittest.TestCase):
	def remote(self, **extra):
		doc = build(2, 1)
		doc["time_logs"][0]["description"] = "Fixed bug\n\nJira: ABC-1 — thing [To Do]\nRef: javascript:alert(1)\n\nRef: https://github.com/o/r/pull/3647"
		doc.update(name="TS-1", docstatus=1, modified="2026-09-08 18:02:11.123456", note="<div class=\"ql-editor\"><p>Day.</p><p>Total hours logged: 3h.</p></div>")
		doc.update(extra)
		return doc

	def pull(self, client, tmp, **kwargs):
		kwargs.setdefault("name", "TS-1")
		return lc.run_pull(client, site=SITE, out_dir=tmp, out=silent, **kwargs)

	def test_pull_writes_files_and_stays_read_only(self):
		with TempHomeDir() as tmp:
			client = client_with({**self.remote()})
			result = self.pull(client, tmp)
			self.assertEqual(client.writes(), [])
			for path in (result["remote"], result["spec"]):
				self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
			remote = json.loads(Path(result["remote"]).read_text())
			self.assertEqual(remote["modified"], "2026-09-08 18:02:11.123456")
			self.assertNotIn("owner", remote)

	def test_spec_recovers_links_pins_hours_and_projects_and_strips_the_note(self):
		with TempHomeDir() as tmp:
			client = client_with({**self.remote()})
			spec_doc = json.loads(Path(self.pull(client, tmp)["spec"]).read_text())
		first = spec_doc["entries"][0]
		self.assertEqual(first["links"], [{"label": "PR-3647", "url": "https://github.com/o/r/pull/3647"}])
		self.assertIn("Jira: ABC-1", first["description"])  # verbatim
		self.assertNotIn("Ref: https", first["description"])
		self.assertEqual((first["tickets"], first["hours"], first["project"]), ([], 2.0, "PROJ-0019"))
		self.assertEqual(spec_doc["note"], "Day.\nTotal hours logged: 3h.")
		self.assertEqual(spec_doc["source"]["modified"], "2026-09-08 18:02:11.123456")
		self.assertEqual(spec_doc["start_time"], "09:30")

	def test_unedited_pulled_spec_rebuilds_to_the_same_rows_and_no_duplicate_refs(self):
		with TempHomeDir() as tmp:
			client = client_with({**self.remote()})
			spec_doc = json.loads(Path(self.pull(client, tmp)["spec"]).read_text())
		rebuilt, _ = ts.build_timesheet(spec_doc, PROFILE, ACTIVITY_TYPES, PROJECTS)
		again, _ = ts.build_timesheet(spec_doc, PROFILE, ACTIVITY_TYPES, PROJECTS)
		self.assertEqual(rebuilt, again)
		original = self.remote()
		for old, new in zip(original["time_logs"], rebuilt["time_logs"]):
			self.assertEqual((old["activity_type"], old["hours"], old["project"]), (new["activity_type"], new["hours"], new["project"]))
		self.assertEqual(rebuilt["time_logs"][0]["description"].count("Ref: https://github.com/o/r/pull/3647"), 1)
		self.assertEqual([link["url"] for link in spec_doc["entries"][0]["links"]], ["https://github.com/o/r/pull/3647"])

	def test_edit_then_diff_shows_only_the_edited_row(self):
		with TempHomeDir() as tmp:
			client = client_with({**self.remote(docstatus=0)})
			spec_doc = json.loads(Path(self.pull(client, tmp)["spec"]).read_text())
		spec_doc["entries"][1]["hours"] = 1.5
		rebuilt, _ = ts.build_timesheet(spec_doc, PROFILE, ACTIVITY_TYPES, PROJECTS)
		diff = lc.diff_docs(lc.normalise_remote(client.docs["TS-1"]), rebuilt)
		self.assertEqual([row["idx"] for row in diff["rows"]["changed"]], [2])
		self.assertEqual(diff["rows"]["changed"][0]["hours"], [1.0, 1.5])

	def test_very_long_names_cannot_overflow_the_filename_and_stay_distinct(self):
		with TempHomeDir() as tmp:
			names = ["TS-" + "x" * 400 + suffix for suffix in ("-1", "-2")]
			client = client_with(*[{**self.remote(), "name": name} for name in names])
			paths = [self.pull(client, tmp, name=name)["spec"] for name in names]
			self.assertEqual(len(set(paths)), 2)
			for path in paths:
				self.assertLess(len(Path(path).name), 200)
				self.assertTrue(Path(path).exists())

	def test_unwritable_out_dir_is_a_suite_error(self):
		with TempHomeDir() as tmp:
			tmp.parent.joinpath("out").write_text("a file, not a directory")
			client = client_with({**self.remote()})
			with self.assertRaises(ts_common.SuiteError):
				self.pull(client, tmp)

	def test_by_date_prefers_the_active_sheet_and_ambiguity_is_exit_2(self):
		with TempHomeDir() as tmp:
			client = client_with({**self.remote(docstatus=2, name="TS-1")}, {**self.remote(docstatus=0, name="TS-2")})
			self.assertEqual(self.pull(client, tmp, name=None, date="2026-09-08", employee=EMPLOYEE)["name"], "TS-2")
			client = client_with({**self.remote(docstatus=0, name="TS-1")}, {**self.remote(docstatus=1, name="TS-2")})
			with self.assertRaises(lc.LifecycleError) as caught:
				self.pull(client, tmp, name=None, date="2026-09-08", employee=EMPLOYEE)
			self.assertEqual(caught.exception.exit_code, 2)

	def test_gaps_and_reconstructed_summaries_are_warned(self):
		doc = self.remote()
		doc["time_logs"][1]["from_time"] = "2026-09-08 15:00:00"
		_, warnings = lc.spec_from_remote(doc, SITE)
		self.assertTrue(any("back to back" in w for w in warnings))
		self.assertTrue(any("chat" in w for w in warnings))
		self.assertTrue(any("amend" in w for w in warnings))


class TempHomeDir:
	def __enter__(self):
		import tempfile

		self.tmp = tempfile.TemporaryDirectory()
		return Path(self.tmp.name) / "out"

	def __exit__(self, *exc):
		self.tmp.cleanup()


def run_cli(env, *argv):
	parser = argparse.ArgumentParser(allow_abbrev=False)
	handlers = lc.add_parsers(parser.add_subparsers(dest="command", required=True))
	args = parser.parse_args(list(argv))
	return handlers[args.command](args, env)


def make_env(client, lines=None):
	return Env(
		load_profile=lambda: dict(PROFILE, out_dir=str(Path(os.environ["TIMESHEET_SUITE_HOME"]) / "out")),
		read_profile=lambda: dict(PROFILE),
		client_factory=lambda site: client,
		out=(lines.append if lines is not None else silent),
	)


class CliTests(TempHome):
	def test_abbreviated_confirm_never_satisfies_a_specific_flag(self):
		parser = argparse.ArgumentParser(allow_abbrev=False)
		handlers = lc.add_parsers(parser.add_subparsers(dest="command", required=True))
		self.assertEqual(sorted(handlers), ["amend", "cancel", "pull", "submit", "sync", "update"])
		cases = [
			["submit", "TS-1", "--confirm", "TS-1"],
			["cancel", "TS-1", "--confirm", "TS-1"],
			["sync", "t.json", "--confirm", "x"],
			["update", "TS-1", "t.json", "--confirm", "TS-1"],
			["amend", "TS-1", "t.json", "--confirm", "TS-1"],
			["submit", "TS-1", "--confirm-sub", "TS-1"],
			["pull", "--na", "TS-1"],
		]
		for argv in cases:
			with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
				parser.parse_args(argv)

	def test_exit_codes_and_json_output(self):
		client = client_with({"name": "TS-1", "docstatus": 1})
		stdout, stderr = io.StringIO(), io.StringIO()
		with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
			code = run_cli(make_env(client), "cancel", "TS-1", "--json")
		result = json.loads(stdout.getvalue())
		self.assertEqual((code, result["status"], result["site"]), (0, "dry_run", PROFILE["site"]))
		self.assertEqual(result["confirm_token"], "TS-1")
		stdout, stderr = io.StringIO(), io.StringIO()
		with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
			code = run_cli(make_env(client), "cancel", "TS-1", "--confirm-cancel", "WRONG", "--expect-modified", "x", "--json")
		self.assertEqual(code, 2)
		self.assertEqual(json.loads(stdout.getvalue())["code"], "confirmation_required")
		self.assertEqual(client.writes(), [])

	def test_applied_mutation_appends_one_private_audit_line_without_secrets(self):
		client = client_with({"name": "TS-1", "docstatus": 1})
		with mock.patch.dict(os.environ, {"FRAPPE_API_SECRET": "sentinel-secret-9876"}):
			code = run_cli(make_env(client), "cancel", "TS-1", "--confirm-cancel", "TS-1", "--expect-modified", modified(client, "TS-1"))
			dry = run_cli(make_env(client), "cancel", "TS-1")
		self.assertEqual((code, dry), (0, 0))
		path = self.home / "audit.log"
		lines = path.read_text().splitlines()
		self.assertEqual(len(lines), 1)
		record = json.loads(lines[0])
		self.assertEqual((record["command"], record["doc"], record["status"]), ("cancel", "TS-1", "cancelled"))
		self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
		self.assertNotIn("sentinel", lines[0])

	def test_unwritable_audit_log_warns_but_does_not_block(self):
		(self.home / "audit.log").mkdir()  # opening a directory for append fails
		client = client_with({"name": "TS-1", "docstatus": 1})
		lines = []
		code = run_cli(make_env(client, lines), "cancel", "TS-1", "--confirm-cancel", "TS-1", "--expect-modified", modified(client, "TS-1"))
		self.assertEqual((code, client.docs["TS-1"]["docstatus"]), (0, 2))
		self.assertTrue(any("audit log" in line for line in lines))

	def test_pull_cli_writes_into_the_profile_out_dir(self):
		client = client_with({**PullTests().remote(), "employee": EMPLOYEE})
		self.assertEqual(run_cli(make_env(client), "pull", "--name", "TS-1"), 0)
		self.assertTrue((self.home / "out" / "edit_TS-1.spec.json").exists())


if __name__ == "__main__":
	unittest.main()
