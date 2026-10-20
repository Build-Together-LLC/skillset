"""Unit tests for ts_profile.py (profile storage and the `profile` commands). Run from the skill folder:

    python3 -m unittest discover -s scripts -p 'test_ts_profile*.py'
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

import ts_common  # noqa: E402
import ts_profile  # noqa: E402
from ts_common import SuiteError  # noqa: E402
from ts_fakes import FakeClient  # noqa: E402
from ts_testkit import PROFILE, TempHome  # noqa: E402

SECRET = "s3cr3t-value-123456"
EMPLOYEES = [
	{"name": "HR-EMP-00001", "employee_name": "Example Employee", "company": "Example Co", "department": "Eng", "status": "Active"},
	{"name": "HR-EMP-00009", "employee_name": "Example Employee", "company": "Other Co", "department": "Ops", "status": "Left"},
]


class Result:
	def __init__(self, code, out, err):
		self.code, self.out, self.err = code, out, err


class ProfileCase(TempHome):
	"""Runs `profile ...` through add_parsers exactly as the composition root does."""

	def run_cli(self, *argv, client=None, factory=None):
		parser = argparse.ArgumentParser(allow_abbrev=False)
		commands = parser.add_subparsers(dest="command", required=True)
		handlers = ts_profile.add_parsers(commands)
		args = parser.parse_args(["profile", *argv])
		env = ts_common.Env(
			load_profile=ts_profile.load_profile,
			read_profile=ts_profile.read_profile,
			client_factory=factory or (lambda site: client),
		)
		out, err = io.StringIO(), io.StringIO()
		with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
			try:
				code = handlers["profile"](args, env)
			except SuiteError as exc:
				print(f"error: {exc}", file=sys.stderr)
				code = exc.exit_code
		return Result(code, out.getvalue(), err.getvalue())

	def write_raw(self, data) -> Path:
		path = ts_profile.profile_path()
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
		return path


class ProfileTests(ProfileCase):
	def test_round_trip_normalises_start_time(self):
		ts_profile.save_profile({**PROFILE, "start_time": "9:30 am"})
		self.assertEqual(ts_profile.load_profile()["start_time"], "09:30:00")

	def test_partial_update_keeps_other_fields(self):
		ts_profile.save_profile(PROFILE)
		ts_profile.save_profile({"project": "Acme Rollout", "company": None})
		profile = ts_profile.load_profile()
		self.assertEqual(profile["project"], "Acme Rollout")
		self.assertEqual(profile["company"], PROFILE["company"])

	def test_rejects_non_profile_fields_such_as_credentials(self):
		with self.assertRaisesRegex(SuiteError, "api_key"):
			ts_profile.save_profile({"api_key": "secret"})

	def test_missing_profile_or_required_fields_raise(self):
		with self.assertRaisesRegex(SuiteError, "No profile yet"):
			ts_profile.load_profile()
		ts_profile.save_profile({"employee_name": "Only Name"})
		with self.assertRaisesRegex(SuiteError, "missing"):
			ts_profile.load_profile()

	def test_unrecognised_time_raises(self):
		with self.assertRaises(SuiteError):
			ts_common.normalise_time("half past nine")

	def test_profile_show_exit_code_signals_first_run(self):
		self.assertEqual(self.run_cli("show").code, 2)
		ts_profile.save_profile(PROFILE)
		self.assertEqual(self.run_cli("show").code, 0)


class RequiredFieldTests(ProfileCase):
	def test_site_is_required_and_never_defaulted(self):
		without_site = {key: value for key, value in PROFILE.items() if key != "site"}
		ts_profile.save_profile(without_site)
		with self.assertRaisesRegex(SuiteError, "site"):
			ts_profile.load_profile()
		self.assertNotIn("site", ts_profile.read_profile())

	def test_missing_profile_is_a_setup_error_not_a_crash(self):
		with self.assertRaises(SuiteError) as caught:
			ts_profile.load_profile()
		self.assertEqual(caught.exception.exit_code, 2)

	def test_chat_targets_are_not_required_to_load(self):
		ts_profile.save_profile({key: value for key, value in PROFILE.items() if key != "chat_targets"})
		self.assertIsNone(ts_profile.load_profile().get("chat_targets"))

	def test_show_lists_exactly_the_missing_fields_one_per_line(self):
		ts_profile.save_profile({"employee_name": "Only Name", "project": "PROJ-1"})
		result = self.run_cli("show")
		missing = [line for line in result.out.splitlines() if line.startswith("missing:")]
		self.assertEqual(result.code, 2)
		self.assertEqual(missing, [f"missing: {field}" for field in ("site", "employee", "company", "start_time", "chat_targets")])

	def test_show_distinguishes_never_asked_from_no_chat(self):
		complete = {key: value for key, value in PROFILE.items() if key != "chat_targets"}
		ts_profile.save_profile(complete)
		never_asked = self.run_cli("show")
		self.assertEqual(never_asked.code, 2)
		self.assertIn("missing: chat_targets", never_asked.out)
		ts_profile.save_profile({"chat_targets": []})
		none_wanted = self.run_cli("show")
		self.assertEqual(none_wanted.code, 0)
		self.assertNotIn("missing:", none_wanted.out)

	def test_unreadable_or_non_object_profiles_are_corrupt_not_a_crash(self):
		path = ts_profile.profile_path()
		path.parent.mkdir(parents=True, exist_ok=True)
		for payload in (b"\xff\xfe\x00\x80binary\xc3\x28", b"[1, 2]", b'"text"', b"[" * 100000):
			with self.subTest(payload=payload[:8]):
				path.write_bytes(payload)
				for argv in (("show",), ("set", "--project", "PROJ-1")):
					result = self.run_cli(*argv)
					self.assertEqual(result.code, 1)
					self.assertIn("corrupt", result.err)
					self.assertNotIn("\\xff", result.err)
					self.assertNotIn("binary", result.err)
				self.assertEqual(path.read_bytes(), payload)

	def test_show_reports_corrupt_and_newer_profiles_without_traceback(self):
		self.write_raw("{not json")
		corrupt = self.run_cli("show")
		self.assertEqual(corrupt.code, 1)
		self.assertIn("not valid JSON", corrupt.err)
		self.write_raw({"profile_version": 3, "site": "https://x.com"})
		newer = self.run_cli("show")
		self.assertEqual(newer.code, 1)
		self.assertIn("newer", newer.err)


class UpgradeTests(ProfileCase):
	def test_v1_profile_upgrades_in_memory_without_inventing_chat_targets(self):
		v1 = {key: value for key, value in PROFILE.items() if key != "chat_targets"}
		v1["site"] = "Erp.Example.com"
		path = self.write_raw(v1)
		before = path.read_bytes()
		profile = ts_profile.read_profile()
		self.assertEqual(profile["profile_version"], 2)
		self.assertEqual(profile["site"], "https://erp.example.com")
		self.assertIsNone(profile.get("chat_targets"))
		self.assertEqual(path.read_bytes(), before)

	def test_v1_without_site_stays_incomplete(self):
		self.write_raw({key: value for key, value in PROFILE.items() if key not in ("site", "chat_targets")})
		self.assertNotIn("site", ts_profile.read_profile())
		self.assertIn("missing: site", self.run_cli("show").out)

	def test_unusable_stored_site_is_dropped_so_it_can_be_fixed(self):
		self.write_raw({**PROFILE, "site": "http://remote.example.com"})
		self.assertNotIn("site", ts_profile.read_profile())
		self.assertEqual(self.run_cli("set", "--site", "erp.example.com").code, 0)

	def test_set_stamps_the_version_on_disk(self):
		self.write_raw({"employee_name": "Old Style"})
		self.assertEqual(self.run_cli("set", "--project", "PROJ-1").code, 0)
		on_disk = json.loads(ts_profile.profile_path().read_text())
		self.assertEqual(on_disk["profile_version"], 2)
		self.assertEqual(on_disk["employee_name"], "Old Style")


class SetValidationTests(ProfileCase):
	def test_each_field_is_normalised(self):
		result = self.run_cli(
			"set", "--site", "ERP.Example.com/app/home", "--jira-site", "https://Example.atlassian.net/jira",
			"--jira-email", " me@example.com ", "--chat-targets", "email,Microsoft Teams", "--utc-offset", "+05:30",
		)
		self.assertEqual(result.code, 0, result.err)
		profile = ts_profile.read_profile()
		self.assertEqual(profile["site"], "https://erp.example.com")
		self.assertEqual(profile["jira_site"], "https://example.atlassian.net")
		self.assertEqual(profile["jira_email"], "me@example.com")
		self.assertEqual(profile["chat_targets"], ["gmail", "teams"])
		self.assertIn("site: https://erp.example.com", result.out)

	def test_bad_values_are_refused_and_nothing_is_written(self):
		bad = (
			("--jira-email", "me@example.com:tok"),
			("--jira-site", "https://evil.example.com"),
			("--utc-offset", "IST"),
			("--chat-targets", "carrier-pigeon"),
			("--site", "http://remote.example.com"),
			("--project", "two\nlines"),
		)
		for flag, value in bad:
			with self.subTest(flag=flag):
				result = self.run_cli("set", flag, value)
				self.assertEqual(result.code, 1)
				self.assertFalse(ts_profile.profile_path().exists())

	def test_credential_lookalikes_are_refused_in_any_field_and_never_echoed(self):
		with mock.patch.dict(os.environ, {"FRAPPE_API_SECRET": SECRET}):
			for flag, value in (
				("--project", f"PROJ {SECRET}"),
				("--employee-name", "ghp_abcdefghijklmnop"),
				("--site", f"token {SECRET}"),
				("--jira-email", f"me@example.com:{SECRET}"),
				("--chat-targets", SECRET),
			):
				with self.subTest(flag=flag):
					result = self.run_cli("set", flag, value)
					self.assertEqual(result.code, 1)
					self.assertNotIn(SECRET, result.out + result.err)
					self.assertNotIn("ghp_abcdefghijklmnop", result.out + result.err)
					self.assertFalse(ts_profile.profile_path().exists())

	def test_file_is_private_even_when_the_folder_already_exists_loose(self):
		folder = ts_profile.profile_path().parent
		folder.mkdir(parents=True, exist_ok=True)
		folder.chmod(0o755)
		ts_profile.save_profile(PROFILE)
		self.assertEqual(stat.S_IMODE(os.stat(ts_profile.profile_path()).st_mode), 0o600)
		self.assertEqual(stat.S_IMODE(os.stat(folder).st_mode), 0o700)

	def test_failed_write_leaves_the_previous_profile_intact(self):
		ts_profile.save_profile(PROFILE)
		before = ts_profile.profile_path().read_bytes()
		with mock.patch("os.replace", side_effect=OSError("disk full")), self.assertRaises(SuiteError):
			ts_profile.save_profile({"project": "PROJ-9"})
		self.assertEqual(ts_profile.profile_path().read_bytes(), before)
		self.assertEqual([p.name for p in ts_profile.profile_path().parent.iterdir()], ["profile.json"])

	def test_corrupt_profile_is_never_overwritten(self):
		path = self.write_raw("{broken")
		result = self.run_cli("set", "--project", "PROJ-1")
		self.assertEqual(result.code, 1)
		self.assertEqual(path.read_text(), "{broken")

	def test_blank_values_do_not_erase_and_unset_does(self):
		ts_profile.save_profile({**PROFILE, "department": "Eng", "chat_targets": ["slack"]})
		self.assertEqual(self.run_cli("set", "--department", "", "--chat-targets", " ").code, 0)
		self.assertEqual(self.run_cli("set", "--project-name", "  ").code, 0)
		profile = ts_profile.read_profile()
		self.assertEqual(profile["department"], "Eng")
		self.assertEqual(profile["chat_targets"], ["slack"])
		self.assertEqual(profile["project_name"], PROFILE["project_name"])
		self.assertEqual(self.run_cli("unset", "department", "project_name").code, 0)
		profile = ts_profile.read_profile()
		self.assertNotIn("department", profile)
		self.assertNotIn("project_name", profile)

	def test_unset_cannot_bypass_the_site_guard_or_touch_unknown_fields(self):
		ts_profile.save_profile(PROFILE)
		for field in ("site", "profile_version", "api_key"):
			with self.subTest(field=field):
				self.assertEqual(self.run_cli("unset", field).code, 1)
		self.assertEqual(ts_profile.read_profile()["site"], PROFILE["site"])


class ChatTargetFlagTests(ProfileCase):
	def test_set_add_remove_and_only_literal_none_clears(self):
		self.assertEqual(self.run_cli("set", "--chat-targets", "discord,slack").code, 0)
		self.assertEqual(self.run_cli("set", "--add-chat-targets", "whatsapp,discord").code, 0)
		self.assertEqual(ts_profile.read_profile()["chat_targets"], ["discord", "slack", "whatsapp"])
		self.assertEqual(self.run_cli("set", "--remove-chat-targets", "slack").code, 0)
		self.assertEqual(ts_profile.read_profile()["chat_targets"], ["discord", "whatsapp"])
		self.assertEqual(self.run_cli("set", "--chat-targets", "none").code, 0)
		self.assertEqual(ts_profile.read_profile()["chat_targets"], [])

	def test_mixing_replace_with_add_is_refused(self):
		result = self.run_cli("set", "--chat-targets", "slack", "--add-chat-targets", "teams")
		self.assertEqual(result.code, 1)
		self.assertFalse(ts_profile.profile_path().exists())

	def test_removing_from_a_never_asked_list_does_not_turn_it_into_no_chat(self):
		ts_profile.save_profile({"project": "PROJ-1"})
		self.assertEqual(self.run_cli("set", "--remove-chat-targets", "slack").code, 0)
		self.assertIsNone(ts_profile.read_profile().get("chat_targets"))

	def test_abbreviated_flags_do_not_satisfy_other_flags(self):
		ts_profile.save_profile(PROFILE)
		for abbreviated in ("--confirm", "--chat"):
			with self.subTest(flag=abbreviated), contextlib.redirect_stderr(io.StringIO()):
				with self.assertRaises(SystemExit) as caught:
					self.run_cli("set", "--site", "other.example.com", abbreviated, "x")
				self.assertEqual(caught.exception.code, 2)


class SiteChangeTests(ProfileCase):
	def test_first_site_and_same_site_need_no_confirmation(self):
		self.assertEqual(self.run_cli("set", "--site", "erp.example.com").code, 0)
		self.assertEqual(self.run_cli("set", "--site", "https://ERP.example.com/app").code, 0)

	def test_changing_a_stored_site_needs_the_exact_origin_as_confirmation(self):
		ts_profile.save_profile(PROFILE)
		blocked = self.run_cli("set", "--site", "erp.new.example")
		self.assertEqual(blocked.code, 2)
		self.assertIn("--confirm-site-change https://erp.new.example", blocked.err)
		wrong = self.run_cli("set", "--site", "erp.new.example", "--confirm-site-change", "https://other.example.com")
		self.assertEqual(wrong.code, 2)
		self.assertEqual(ts_profile.read_profile()["site"], PROFILE["site"])
		allowed = self.run_cli("set", "--site", "erp.new.example", "--confirm-site-change", "https://erp.new.example")
		self.assertEqual(allowed.code, 0, allowed.err)
		self.assertEqual(ts_profile.read_profile()["site"], "https://erp.new.example")
		self.assertIn("warning: site changed", allowed.out)

	def test_site_change_is_all_or_nothing(self):
		ts_profile.save_profile(PROFILE)
		self.assertEqual(self.run_cli("set", "--site", "erp.new.example", "--project", "PROJ-77").code, 2)
		self.assertEqual(ts_profile.read_profile()["project"], PROFILE["project"])


class ResolveTests(ProfileCase):
	def test_lists_employees_with_status_warning_and_writes_nothing(self):
		ts_profile.save_profile(PROFILE)
		before = ts_profile.profile_path().read_bytes()
		sites = []
		result = self.run_cli("resolve", factory=lambda site: sites.append(site) or FakeClient(employees=EMPLOYEES))
		self.assertEqual(result.code, 0, result.err)
		self.assertEqual(sites, [PROFILE["site"]])
		for value in ("HR-EMP-00001", "HR-EMP-00009", "Example Co", "Other Co", "Ops", "Eng", "Left", "employee@example.com"):
			self.assertIn(value, result.out)
		warnings = [line for line in result.out.splitlines() if line.startswith("warning:")]
		self.assertEqual(len(warnings), 1)
		self.assertIn("HR-EMP-00009", warnings[0])
		self.assertEqual(ts_profile.profile_path().read_bytes(), before)

	def test_works_before_any_profile_exists_with_an_explicit_site_and_still_writes_nothing(self):
		sites = []
		result = self.run_cli("resolve", "--site", "ERP.example.com", factory=lambda site: sites.append(site) or FakeClient(employees=EMPLOYEES[:1]))
		self.assertEqual(result.code, 0, result.err)
		self.assertEqual(sites, ["https://erp.example.com"])
		self.assertFalse(ts_profile.profile_path().exists())

	def test_without_any_known_site_it_asks_instead_of_guessing(self):
		called = []
		result = self.run_cli("resolve", factory=lambda site: called.append(site))
		self.assertEqual(result.code, 2)
		self.assertIn("missing: site", result.out)
		self.assertEqual(called, [])

	def test_site_flag_cannot_steer_credentials_away_from_the_stored_site(self):
		ts_profile.save_profile(PROFILE)
		called = []
		result = self.run_cli("resolve", "--site", "evil.example.com", factory=lambda site: called.append(site))
		self.assertEqual(result.code, 2)
		self.assertIn("--confirm-site-change", result.err)
		self.assertEqual(called, [])
		same = self.run_cli("resolve", "--site", "erp.example.com", client=FakeClient(employees=EMPLOYEES[:1]))
		self.assertEqual(same.code, 0, same.err)

	def test_no_employee_and_forbidden_lookups_give_actionable_errors(self):
		ts_profile.save_profile(PROFILE)
		empty = self.run_cli("resolve", client=FakeClient(employees=[]))
		self.assertEqual(empty.code, 1)
		self.assertIn("employee@example.com", empty.err)
		self.assertIn("type the details", empty.err)

		class Forbidden(FakeClient):
			def employees_for_user(self, user):
				error = SuiteError("403 Forbidden: secret server detail")
				error.status = 403
				raise error

		denied = self.run_cli("resolve", client=Forbidden())
		self.assertEqual(denied.code, 1)
		self.assertIn("403", denied.err)
		self.assertIn("type the details", denied.err)

	def test_no_credential_reaches_any_output_or_the_profile(self):
		with mock.patch.dict(os.environ, {"FRAPPE_API_SECRET": SECRET, "JIRA_API_TOKEN": SECRET + "x"}):
			outputs = [
				self.run_cli("set", *sum((["--" + key.replace("_", "-"), str(value)] for key, value in PROFILE.items() if key != "chat_targets"), [])),
				self.run_cli("set", "--chat-targets", "discord"),
				self.run_cli("show"),
				self.run_cli("resolve", client=FakeClient(employees=EMPLOYEES)),
			]
		self.assertTrue(all(result.code == 0 for result in outputs), [r.err for r in outputs])
		text = "".join(result.out + result.err for result in outputs) + ts_profile.profile_path().read_text()
		self.assertNotIn(SECRET, text)


if __name__ == "__main__":
	unittest.main()
