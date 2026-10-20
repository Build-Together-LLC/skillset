"""Integration tests: the real FrappeClient and ts_lifecycle against a loopback record-and-replay HTTP server.

    python3 -m unittest discover -s scripts -p 'test_ts_lifecycle*.py'
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import timesheet_suite as ts  # noqa: E402  (build_timesheet only)
import ts_lifecycle as lc  # noqa: E402
from ts_common import Env  # noqa: E402
from ts_http_fake import HttpFake  # noqa: E402
from ts_frappe import FrappeClient, FrappeError  # noqa: E402
from ts_testkit import ACTIVITY_TYPES, PROFILE, PROJECTS, TempHome, entry, silent, spec  # noqa: E402

SECRET = "sentinel-secret-9876543"
MODIFIED = "2026-09-08 18:02:11.123456"
EMPLOYEE = "HR-EMP-00001"


def doc(docstatus=0, **extra):
	built, _ = ts.build_timesheet(spec([entry(hours=2)]), PROFILE, ACTIVITY_TYPES, PROJECTS)
	return {**built, "name": "TS-1", "docstatus": docstatus, "modified": MODIFIED, "owner": "x", **extra}


def stock(site: HttpFake, remote: dict) -> None:
	site.reply("GET", "/api/method/frappe.auth.get_logged_user", {"message": "employee@example.com"})
	site.reply("GET", "/api/resource/Employee", {"data": [{"name": EMPLOYEE, "employee_name": "Example Employee"}]})
	site.reply("GET", "/api/resource/Timesheet", {"data": [{k: remote[k] for k in ("name", "docstatus", "modified", "start_date", "end_date", "total_hours")}]})
	site.reply("GET", "/api/resource/Timesheet/TS-1", {"data": remote})
	site.reply("GET", "/api/method/frappe.desk.form.load.getdoctype", {"docs": [{"name": "Timesheet", "__workflow_docs": []}]})
	site.reply("GET", "/api/method/frappe.client.has_permission", {"message": {"has_permission": True}})


class LifecycleHttpTests(TempHome):
	def setUp(self):
		super().setUp()
		patcher = mock.patch.dict(os.environ, {"FRAPPE_API_SECRET": SECRET})
		patcher.start()
		self.addCleanup(patcher.stop)
		self.site = HttpFake().start()
		self.addCleanup(self.site.stop)

	def client(self):
		return FrappeClient(self.site.url, api_key="key", api_secret=SECRET)

	def test_dry_runs_make_zero_non_get_requests(self):
		stock(self.site, doc(0, total_hours=2.0))
		client = self.client()
		lc.run_sync(client, doc(0), site=self.site.url, out=silent)
		lc.run_update(client, "TS-1", doc(0, note="changed"), site=self.site.url, out=silent)
		lc.run_cancel(client, "TS-1", site=self.site.url, out=silent)
		lc.run_submit(client, "TS-1", site=self.site.url, out=silent)
		self.assertEqual(self.site.non_get(), [])

	def test_update_sends_the_modified_it_read_and_the_submit_body_is_the_full_doc(self):
		remote = doc(0, total_hours=2.0)
		stock(self.site, remote)
		self.site.reply("PUT", "/api/resource/Timesheet/TS-1", {"data": remote})
		client = self.client()
		lc.run_update(
			client, "TS-1", doc(0, note="changed"), site=self.site.url,
			confirm_update="TS-1", expect_modified=MODIFIED, out=silent,
		)
		body = self.site.requests_to("PUT", "/api/resource/Timesheet/TS-1")[0].json()
		self.assertEqual(body["modified"], MODIFIED)
		self.assertNotIn("doctype", body)
		self.site.reply("POST", "/api/method/frappe.client.submit", {"message": {**remote, "docstatus": 1}})
		self.site.reply("GET", "/api/resource/Timesheet/TS-1", {"data": {**remote, "docstatus": 1}})
		lc.run_submit(client, "TS-1", site=self.site.url, confirm_submit="TS-1", expect_modified=MODIFIED, out=silent)
		sent = json.loads(self.site.requests_to("POST", "/api/method/frappe.client.submit")[0].json()["doc"])
		self.assertEqual((sent["name"], sent["modified"], len(sent["time_logs"])), ("TS-1", MODIFIED, 1))

	def test_server_conflict_is_reported_with_its_normalised_code(self):
		stock(self.site, doc(0, total_hours=2.0))
		self.site.reply(
			"PUT", "/api/resource/Timesheet/TS-1",
			{"exc_type": "TimestampMismatchError", "_server_messages": json.dumps([json.dumps({"message": "Document has been modified"})])},
			status=417,
		)
		with self.assertRaises(FrappeError) as caught:
			lc.run_update(self.client(), "TS-1", doc(0, note="x"), site=self.site.url, confirm_update="TS-1", expect_modified=MODIFIED, out=silent)
		self.assertEqual(caught.exception.code, "conflict")

	def test_cross_origin_redirect_never_receives_the_credentials(self):
		other = HttpFake().start()
		self.addCleanup(other.stop)
		self.site.reply("GET", "/api/method/frappe.auth.get_logged_user", None, status=302, headers={"Location": other.url + "/steal"})
		other.reply("GET", "/steal", {"message": "x"})
		with self.assertRaises(FrappeError):
			self.client().logged_user()
		self.assertEqual(other.requests, [])

	def test_secret_never_appears_in_output_audit_or_files_even_on_errors(self):
		remote = doc(1, total_hours=2.0)
		stock(self.site, remote)
		self.site.reply("POST", "/api/method/frappe.client.cancel", {"exc_type": "PermissionError", "exception": f"Not permitted {SECRET}"}, status=403)
		self.site.reply("POST", "/api/method/frappe.model.workflow.get_transitions", {"message": []})
		client, out = self.client(), io.StringIO()
		env = Env(
			load_profile=lambda: dict(PROFILE, site=self.site.url, out_dir=str(self.home / "out")),
			read_profile=lambda: dict(PROFILE),
			client_factory=lambda site: client,
			out=lambda line: print(line, file=out),
		)
		import argparse

		parser = argparse.ArgumentParser(allow_abbrev=False)
		handlers = lc.add_parsers(parser.add_subparsers(dest="command"))
		for argv in (["cancel", "TS-1"], ["cancel", "TS-1", "--confirm-cancel", "TS-1", "--expect-modified", MODIFIED, "--json"], ["pull", "--name", "TS-1"]):
			args = parser.parse_args(argv)
			stdout, stderr = io.StringIO(), io.StringIO()
			with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
				handlers[args.command](args, env)
			out.write(stdout.getvalue() + stderr.getvalue())
		blob = out.getvalue()
		for path in self.home.rglob("*"):
			if path.is_file():
				blob += path.read_text()
		self.assertNotIn(SECRET, blob)
		self.assertIn("redacted", blob)  # the server echoed it; the client scrubbed it


if __name__ == "__main__":
	unittest.main()
