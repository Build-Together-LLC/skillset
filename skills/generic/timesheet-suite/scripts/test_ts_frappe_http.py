"""Integration tests: the real FrappeClient against a record-and-replay loopback server. No external network."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ts_common  # noqa: E402
import ts_frappe  # noqa: E402
from ts_http_fake import HttpFake  # noqa: E402
from ts_frappe import FrappeError  # noqa: E402

KEY, SECRET = "key-1a2b3c", "sekrit-" + "7d8e9f00"
TS = "/api/resource/Timesheet/TS-1"


class HttpCase(unittest.TestCase):
	def setUp(self):
		self.site = HttpFake().start()
		self.addCleanup(self.site.stop)
		self.client = ts_frappe.FrappeClient(self.site.url, api_key=KEY, api_secret=SECRET)


class ReadOnlyFlowTests(HttpCase):
	def test_reading_never_makes_a_non_get_call(self):
		site = self.site
		site.reply("GET", "/api/method/frappe.auth.get_logged_user", {"message": "a@b.c"})
		site.reply("GET", "/api/resource/Employee", {"data": [{"name": "HR-EMP-00001"}]})
		site.reply("GET", "/api/resource/Timesheet", {"data": [{"name": "TS-1", "docstatus": 0}]})
		site.reply("GET", TS, {"data": {"name": "TS-1", "modified": "2026-09-08 10:00:00.123456", "docstatus": 0}})
		site.reply("GET", "/api/method/frappe.desk.form.load.getdoctype", {"docs": [{"name": "Timesheet", "__workflow_docs": []}]})
		site.reply("GET", "/api/method/frappe.client.has_permission", {"message": {"has_permission": True}})
		client = self.client
		client.logged_user()
		client.employees_for_user("a@b.c")
		client.timesheets_for("HR-EMP-00001", "2026-09-08")
		doc = client.get_timesheet("TS-1")
		self.assertIsNone(client.workflow_for("Timesheet", doc))
		self.assertTrue(client.has_permission("Timesheet", "TS-1", "submit"))
		self.assertEqual(site.non_get(), [])
		self.assertEqual(len(site.requests), 6)
		self.assertEqual(site.requests[0].headers["authorization"], f"token {KEY}:{SECRET}")


class ModifiedRoundTripTests(HttpCase):
	def test_modified_read_from_get_is_sent_back_unchanged(self):
		modified = "2026-09-08 10:00:00.123456"
		self.site.reply("GET", TS, {"data": {"name": "TS-1", "modified": modified, "docstatus": 0}})
		self.site.reply("PUT", TS, {"data": {"name": "TS-1", "modified": "2026-09-08 10:05:00.000001"}})
		doc = self.client.get_timesheet("TS-1")
		self.client.update_timesheet("TS-1", {"note": "new"}, doc["modified"])
		(put,) = self.site.requests_to("PUT", TS)
		self.assertEqual(put.json(), {"note": "new", "modified": modified})
		self.assertEqual(put.headers["content-type"], "application/json")

	def test_a_stale_write_is_reported_as_a_conflict(self):
		self.site.reply(
			"PUT",
			TS,
			{"exc_type": "TimestampMismatchError", "_server_messages": json.dumps([json.dumps({"message": "Document has been modified after you have opened it"})])},
			status=417,
		)
		with self.assertRaises(FrappeError) as caught:
			self.client.update_timesheet("TS-1", {"note": "x"}, "old")
		self.assertEqual((caught.exception.code, caught.exception.status), ("conflict", 417))

	def test_submit_and_delete_wire_format(self):
		self.site.reply("POST", "/api/method/frappe.client.submit", {"message": {"name": "TS-1", "docstatus": 1}})
		self.site.reply("DELETE", TS, {"message": "ok"}, status=202)
		doc = {"name": "TS-1", "modified": "m1", "time_logs": [{"hours": 1}]}
		self.client.submit_doc(doc)
		self.client.delete_timesheet("TS-1")
		(submit,) = self.site.requests_to("POST", "/api/method/frappe.client.submit")
		self.assertEqual(json.loads(submit.json()["doc"]), doc)
		self.assertEqual(len(self.site.requests_to("DELETE", TS)), 1)


class RedirectTests(HttpCase):
	def setUp(self):
		super().setUp()
		self.evil = HttpFake().start()
		self.addCleanup(self.evil.stop)

	def test_cross_origin_redirect_never_receives_credentials(self):
		self.site.reply("GET", TS, "", status=302, headers={"Location": f"{self.evil.url}/steal"})
		self.evil.reply("GET", "/steal", {"data": {}})
		with self.assertRaises(FrappeError) as caught:
			self.client.get_timesheet("TS-1")
		self.assertEqual(self.evil.requests, [])
		self.assertEqual(caught.exception.code, "redirect")
		self.assertNotIn(SECRET, str(caught.exception))

	def test_a_write_is_never_replayed_through_a_redirect(self):
		self.site.reply("POST", "/api/resource/Timesheet", "", status=307, headers={"Location": f"{self.site.url}/elsewhere"})
		self.site.reply("POST", "/elsewhere", {"data": {"name": "TS-X"}})
		with self.assertRaises(FrappeError):
			self.client.create_timesheet({"employee": "E"})
		self.assertEqual(self.site.requests_to("POST", "/elsewhere"), [])

	def test_same_origin_get_redirect_is_followed_with_credentials(self):
		self.site.reply("GET", TS, "", status=302, headers={"Location": "/moved"})
		self.site.reply("GET", "/moved", {"data": {"name": "TS-1"}})
		self.assertEqual(self.client.get_timesheet("TS-1")["name"], "TS-1")
		self.assertEqual(self.site.requests_to("GET", "/moved")[0].headers["authorization"], f"token {KEY}:{SECRET}")


class SecretAndProxyTests(HttpCase):
	def test_secret_never_appears_in_any_error(self):
		self.site.reply("GET", TS, {"exception": f"Invalid token {KEY}:{SECRET}"}, status=401)
		self.site.reply("GET", "/boom", "not json", status=502)
		with mock.patch.dict(os.environ, {"FRAPPE_API_SECRET": SECRET}):
			failures = []
			for call in (lambda: self.client.get_timesheet("TS-1"), lambda: self.client._request("GET", "/boom")):
				with self.assertRaises(FrappeError) as caught:
					call()
				failures.append(caught.exception)
		for error in failures:
			for text in (str(error), repr(error), error.detail):
				self.assertNotIn(SECRET, text)
		self.assertEqual([error.code for error in failures], ["auth", "server"])

	def test_loopback_site_ignores_proxy_environment_variables(self):
		proxy = HttpFake().start()
		self.addCleanup(proxy.stop)
		proxy.reply("GET", TS, {"data": {"name": "from-proxy"}})
		self.site.reply("GET", TS, {"data": {"name": "direct"}})
		env = {"http_proxy": proxy.url, "HTTP_PROXY": proxy.url}
		with mock.patch.dict(os.environ, env):
			os.environ.pop("no_proxy", None)
			os.environ.pop("NO_PROXY", None)
			client = ts_frappe.FrappeClient(self.site.url, api_key=KEY, api_secret=SECRET)
			doc = client.get_timesheet("TS-1")
		self.assertEqual(doc["name"], "direct")
		self.assertEqual(proxy.requests, [])


class PasswordLoginTests(HttpCase):
	def test_password_login_posts_credentials_once_and_keeps_the_cookie(self):
		self.site.reply("POST", "/api/method/login", {"message": "Logged In"}, headers={"Set-Cookie": "sid=abc; Path=/"})
		self.site.reply("GET", "/api/method/frappe.auth.get_logged_user", {"message": "a@b.c"})
		client = ts_frappe.FrappeClient(self.site.url, user="a@b.c", password=SECRET)
		client.logged_user()
		self.assertEqual(len(self.site.requests_to("POST", "/api/method/login")), 1)
		self.assertIn("sid=abc", self.site.requests_to("GET", "/api/method/frappe.auth.get_logged_user")[0].headers.get("cookie", ""))
		self.assertNotIn("authorization", self.site.requests[-1].headers)


if __name__ == "__main__":
	unittest.main()
