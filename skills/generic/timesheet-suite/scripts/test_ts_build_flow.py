"""Integration tests: the real `main()` end to end with fake clients and no network. Run from the skill folder:

    python3 -m unittest discover -s scripts

Covered flows: first run (profile -> build with Jira digest and three chat apps), v1 profile migration, catalogue
refresh -> build uses the cache, create -> pull -> build -> update round trip, and the submit gate.
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

import timesheet_suite as ts  # noqa: E402
import ts_catalogue  # noqa: E402
import ts_frappe  # noqa: E402
from ts_fakes import FakeClient  # noqa: E402
from ts_testkit import PROFILE, TempHome, entry, spec  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "assets"
DEFAULT_SITE = "https://erp.example.com"
EMPLOYEE = PROFILE["employee"]
PROFILE_FLAGS = [
	"--employee-name", "Example Employee", "--employee", EMPLOYEE, "--company", PROFILE["company"],
	"--project", PROFILE["project"], "--project-name", PROFILE["project_name"], "--start-time", "09:30",
]


class FlowCase(TempHome):
	"""Runs `main()` for real; any site client the command asks for is the test's fake."""

	client: FakeClient | None = None

	def run_main(self, *argv, client=None):
		stdout, stderr = io.StringIO(), io.StringIO()
		factory = mock.patch.object(ts_frappe.FrappeClient, "from_env", side_effect=lambda site: client or self.client)
		with factory, contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
			code = ts.main([str(part) for part in argv])
		return code, stdout.getvalue(), stderr.getvalue()

	def set_profile(self, site=DEFAULT_SITE, targets="discord", *extra):
		code, _, stderr = self.run_main("profile", "set", "--site", site, *PROFILE_FLAGS, "--chat-targets", targets, *extra)
		self.assertEqual((code, stderr), (0, ""))

	def write_spec(self, document, name="spec.json"):
		path = self.home / name
		path.write_text(json.dumps(document))
		return path

	def names(self, folder):
		return sorted(path.name for path in Path(folder).iterdir())


class FirstRunTests(FlowCase):
	def test_profile_then_build_with_a_jira_digest_writes_the_json_and_three_chat_messages(self):
		self.set_profile(DEFAULT_SITE, "discord,slack,gmail")
		sample = json.loads((ASSETS / "sample_spec.json").read_text(encoding="utf-8"))
		sample["entries"][0]["tickets"] = ["BILL-101"]
		out = self.home / "out"
		out.mkdir()
		(out / "jira_2026-01-15.json").write_text((ASSETS / "sample_jira_digest.json").read_text(encoding="utf-8"))
		code, stdout, stderr = self.run_main("build", self.write_spec(sample), "--out-dir", out)
		self.assertEqual((code, stderr), (0, ""))
		date = "2026-01-15"
		self.assertEqual(
			self.names(out),
			sorted([
				f"timesheet_{date}.json", f"jira_{date}.json", f"discord_{date}.md", f"chat_slack_{date}.txt",
				f"chat_gmail_{date}.html", f"chat_gmail_{date}.txt",
			]),
		)
		doc = json.loads((out / f"timesheet_{date}.json").read_text())
		row = doc["time_logs"][0]["description"]
		self.assertIn("Jira: BILL-101", row)
		self.assertEqual(row.count("Ref: https://github.com/example-org/example-repo/pull/101"), 1)
		for name in (f"discord_{date}.md", f"chat_slack_{date}.txt", f"chat_gmail_{date}.html"):
			with self.subTest(name):
				self.assertIn("BILL-101", (out / name).read_text())
		for target in ("discord", "slack", "gmail"):
			self.assertRegex(stdout, rf"{target}: .* · \d+/\d+ (chars|utf16|bytes) · links embedded \d+/\d+")
		self.assertIn("catalogue: none", stdout)

	def test_no_credentials_or_secrets_end_up_under_the_config_dir(self):
		secrets = {"FRAPPE_API_KEY": "key-sentinel-123456", "FRAPPE_API_SECRET": "secret-sentinel-123456", "JIRA_API_TOKEN": "jira-sentinel-123456"}
		with mock.patch.dict(os.environ, secrets):
			self.set_profile(DEFAULT_SITE, "discord")
			self.run_main("build", self.write_spec(spec([entry()])), "--out-dir", self.home / "out")
		for path in self.home.rglob("*"):
			if path.is_file():
				for value in secrets.values():
					self.assertNotIn(value, path.read_text())


class V1ProfileMigrationTests(FlowCase):
	def v1_profile(self):
		(self.home / "profile.json").write_text(json.dumps({
			"employee_name": "Example Employee", "employee": EMPLOYEE, "company": PROFILE["company"],
			"project": PROFILE["project"], "start_time": "09:30:00",
		}))

	def test_a_v1_profile_is_incomplete_until_the_site_and_chat_apps_are_given(self):
		self.v1_profile()
		code, stdout, _ = self.run_main("profile", "show")
		self.assertEqual(code, 2)
		self.assertIn("missing: site", stdout)
		self.assertIn("missing: chat_targets", stdout)
		self.assertNotIn("missing: employee", stdout)
		code, _, stderr = self.run_main("build", self.write_spec(spec([entry()])), "--out-dir", self.home / "out")
		self.assertEqual(code, 2)
		self.assertIn("site", stderr)
		self.assertFalse((self.home / "out").exists())

	def test_answering_only_the_missing_fields_makes_the_old_profile_build(self):
		self.v1_profile()
		code, _, stderr = self.run_main("profile", "set", "--site", "erp.example.com", "--chat-targets", "whatsapp")
		self.assertEqual((code, stderr), (0, ""))
		self.assertEqual(self.run_main("profile", "show")[0], 0)
		out = self.home / "out"
		self.assertEqual(self.run_main("build", self.write_spec(spec([entry()])), "--out-dir", out)[0], 0)
		self.assertEqual(self.names(out), ["chat_whatsapp_2026-09-08.txt", "timesheet_2026-09-08.json"])


class CatalogueRefreshTests(FlowCase):
	SITE = "https://erp.example.com"

	def site_client(self):
		return FakeClient(records={
			"Activity Type": [{"name": "Site Only Type", "disabled": 0}, {"name": "Coding", "disabled": 0}],
			"Project": [{"name": "PROJ-0019", "project_name": "Example Project", "status": "Open"}],
			"Company": [{"name": PROFILE["company"], "default_currency": "USD"}],
		})

	def build_doc(self, activity):
		code, stdout, stderr = self.run_main(
			"build", self.write_spec(spec([entry(activity_type=activity)])), "--out-dir", self.home / "out"
		)
		return code, stdout, stderr

	def test_without_a_cache_a_foreign_site_is_unvalidated_and_after_refresh_the_cache_is_used(self):
		self.set_profile(self.SITE)
		code, stdout, _ = self.build_doc("Site Only Type")
		self.assertEqual(code, 0)
		self.assertEqual(stdout.count(ts_catalogue.UNVALIDATED_WARNING), 1)
		self.assertEqual(json.loads((self.home / "out" / "timesheet_2026-09-08.json").read_text())["currency"], "INR")

		code, stdout, _ = self.run_main("catalogue", "refresh", client=self.site_client())
		self.assertEqual(code, 0)
		self.assertIn("activity types: 2", stdout)

		code, stdout, _ = self.build_doc("Site Only Type")
		self.assertEqual(code, 0)
		self.assertNotIn(ts_catalogue.UNVALIDATED_WARNING, stdout)
		self.assertIn("catalogue: cache erp.example.com", stdout)
		self.assertEqual(json.loads((self.home / "out" / "timesheet_2026-09-08.json").read_text())["currency"], "USD")

		code, _, stderr = self.build_doc("Review")
		self.assertEqual(code, 1)
		self.assertIn("not a valid Activity Type", stderr)

	def test_a_site_without_a_cache_is_not_validated(self):
		self.set_profile(self.SITE)
		code, stdout, _ = self.build_doc("Coding + Meeting")
		self.assertEqual(code, 0)
		self.assertIn(ts_catalogue.UNVALIDATED_WARNING, stdout)


class RoundTripTests(FlowCase):
	"""build -> sync (create) -> pull -> build -> update: the remote copy rebuilds to the same bytes."""

	def create_remote(self):
		self.set_profile(DEFAULT_SITE, "discord")
		sample = json.loads((ASSETS / "sample_spec.json").read_text(encoding="utf-8"))
		sample["entries"][0]["tickets"] = ["BILL-101"]
		first = self.home / "first"
		first.mkdir()
		(first / "jira_2026-01-15.json").write_text((ASSETS / "sample_jira_digest.json").read_text(encoding="utf-8"))
		self.assertEqual(self.run_main("build", self.write_spec(sample), "--out-dir", first)[0], 0)
		self.client = FakeClient()
		timesheet = first / "timesheet_2026-01-15.json"
		code, stdout, _ = self.run_main("sync", timesheet)
		self.assertEqual(code, 0)
		self.assertEqual(self.client.writes(), [])
		code, _, _ = self.run_main("sync", timesheet, "--confirm-create", f"{EMPLOYEE}/2026-01-15")
		self.assertEqual(code, 0)
		self.assertEqual(self.client.writes(), ["create"])
		return json.loads(timesheet.read_text())

	def test_pull_then_build_twice_is_bytes_stable_with_no_duplicate_ref_and_update_finds_nothing_to_change(self):
		original = self.create_remote()
		pulled = self.home / "pulled"
		code, _, _ = self.run_main("pull", "--name", "TS-NEW", "--out-dir", pulled)
		self.assertEqual(code, 0)
		edit = pulled / "edit_TS-NEW.spec.json"
		builds = []
		for run in ("a", "b"):
			out = self.home / run
			self.assertEqual(self.run_main("build", edit, "--out-dir", out)[0], 0)
			builds.append((out / "timesheet_2026-01-15.json").read_bytes())
		self.assertEqual(builds[0], builds[1])
		rebuilt = json.loads(builds[0])
		for before, after in zip(original["time_logs"], rebuilt["time_logs"]):
			self.assertEqual(
				(before["activity_type"], before["hours"], before["project"], before["description"]),
				(after["activity_type"], after["hours"], after["project"], after["description"]),
			)
			refs = [line for line in after["description"].splitlines() if line.startswith("Ref: ")]
			self.assertEqual(len(refs), len(set(refs)))
		self.assertEqual(rebuilt["note"], original["note"])

		self.client.calls.clear()
		code, stdout, _ = self.run_main("update", "TS-NEW", self.home / "a" / "timesheet_2026-01-15.json")
		self.assertEqual(code, 0)
		self.assertEqual(self.client.writes(), [])

	def test_an_edit_to_the_pulled_spec_shows_up_in_the_update_dry_run_and_is_written_only_with_both_flags(self):
		self.create_remote()
		pulled = self.home / "pulled"
		self.run_main("pull", "--name", "TS-NEW", "--out-dir", pulled)
		edit = pulled / "edit_TS-NEW.spec.json"
		document = json.loads(edit.read_text())
		document["entries"][1]["hours"] = 1.0
		edit.write_text(json.dumps(document))
		out = self.home / "edited"
		self.assertEqual(self.run_main("build", edit, "--out-dir", out)[0], 0)
		timesheet = out / "timesheet_2026-01-15.json"

		self.client.calls.clear()
		code, stdout, _ = self.run_main("update", "TS-NEW", timesheet, "--json")
		self.assertEqual(code, 0)
		self.assertEqual(json.loads(stdout)["status"], "dry_run")
		self.assertEqual(self.client.writes(), [])

		code, _, stderr = self.run_main("update", "TS-NEW", timesheet, "--confirm-update", "TS-NEW")
		self.assertEqual(code, 2)
		self.assertEqual(self.client.writes(), [])

		modified = self.client.docs["TS-NEW"]["modified"]
		code, _, _ = self.run_main("update", "TS-NEW", timesheet, "--confirm-update", "TS-NEW", "--expect-modified", modified)
		self.assertEqual(code, 0)
		self.assertEqual(self.client.writes(), ["update"])
		self.assertEqual(self.client.docs["TS-NEW"]["time_logs"][1]["hours"], 1.0)


class SubmitGateTests(FlowCase):
	def setUp(self):
		super().setUp()
		self.set_profile(DEFAULT_SITE, "discord")
		build = self.home / "built"
		self.assertEqual(self.run_main("build", self.write_spec(spec([entry(hours=2)])), "--out-dir", build)[0], 0)
		self.client = FakeClient()
		self.assertEqual(self.run_main("sync", build / "timesheet_2026-09-08.json", "--confirm-create", f"{EMPLOYEE}/2026-09-08")[0], 0)
		self.name = "TS-NEW"
		self.client.calls.clear()

	def submit(self, *flags):
		return self.run_main("submit", self.name, *flags)

	def test_without_a_confirm_flag_nothing_is_written(self):
		code, stdout, _ = self.submit()
		self.assertEqual(code, 0)
		self.assertEqual(self.client.writes(), [])
		self.assertEqual(self.client.docs[self.name]["docstatus"], 0)
		self.assertIn("--confirm-submit", stdout)

	def test_a_wrong_or_incomplete_confirmation_exits_2_and_writes_nothing(self):
		modified = self.client.docs[self.name]["modified"]
		for flags in (
			("--confirm-submit", "TS-OTHER", "--expect-modified", modified),
			("--confirm-submit", self.name),
			("--confirm-submit", self.name, "--expect-modified", "2000-01-01 00:00:00.000000"),
		):
			with self.subTest(flags):
				code, _, _ = self.submit(*flags)
				self.assertNotEqual(code, 0)
				self.assertNotIn("submit", self.client.writes())
				self.assertEqual(self.client.docs[self.name]["docstatus"], 0)

	def test_the_abbreviated_confirm_flag_is_rejected_before_anything_runs(self):
		modified = self.client.docs[self.name]["modified"]
		with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
			ts.main(["submit", self.name, "--confirm", self.name, "--expect-modified", modified])
		self.assertEqual(stopped.exception.code, 2)
		self.assertEqual(self.client.calls, [])

	def test_the_exact_flag_with_the_name_and_modified_submits_exactly_once(self):
		modified = self.client.docs[self.name]["modified"]
		code, _, _ = self.submit("--confirm-submit", self.name, "--expect-modified", modified)
		self.assertEqual(code, 0)
		self.assertEqual(self.client.writes(), ["submit"])
		self.assertEqual(self.client.docs[self.name]["docstatus"], 1)


if __name__ == "__main__":
	unittest.main()
