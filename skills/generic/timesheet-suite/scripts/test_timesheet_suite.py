"""Unit tests for timesheet_suite.py: hours, schedule, build, build command, GitHub. Run from the skill folder:

    python3 -m unittest discover -s scripts
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import timesheet_suite as ts  # noqa: E402
import ts_common  # noqa: E402
import ts_catalogue  # noqa: E402
import ts_profile  # noqa: E402
from ts_testkit import ACTIVITY_TYPES, PROFILE, PROJECTS, TempHome, entry, spec  # noqa: E402


class HoursTests(unittest.TestCase):
	def test_given_hours_are_kept(self):
		self.assertEqual(ts.resolve_hours([entry(hours=1.5), entry(hours=0.75)], None), [1.5, 0.75])

	def test_given_hours_must_match_the_target(self):
		with self.assertRaisesRegex(ts_common.SuiteError, "target is 3h"):
			ts.resolve_hours([entry(hours=1), entry(hours=1)], 3)

	def test_remainder_is_split_in_quarter_hours_and_last_absorbs_rounding(self):
		self.assertEqual(ts.resolve_hours([entry(hours=2), entry(hours=None), entry(hours=None)], 5), [2.0, 1.5, 1.5])
		self.assertEqual(ts.resolve_hours([entry(hours=None)] * 3, 3.5), [1.0, 1.0, 1.5])

	def test_missing_hours_without_a_target_raise(self):
		with self.assertRaisesRegex(ts_common.SuiteError, "estimate"):
			ts.resolve_hours([entry(hours=None)], None)

	def test_non_positive_hours_raise(self):
		with self.assertRaisesRegex(ts_common.SuiteError, "greater than zero"):
			ts.resolve_hours([entry(hours=0)], None)
		with self.assertRaisesRegex(ts_common.SuiteError, "too little"):
			ts.resolve_hours([entry(hours=4), entry(hours=None)], 4)


class EstimateScalingTests(unittest.TestCase):
	"""`"estimated": true` lets target_total_hours rescale guessed hours; fixed hours are never touched."""

	def fit(self, hours, target, estimated):
		entries = [entry(hours=value, estimated=flag) for value, flag in zip(hours, estimated)]
		return ts.resolve_hours(entries, target)

	def test_estimates_are_scaled_in_quarters_to_the_exact_target(self):
		fitted = self.fit([1, 2, 1, 1], 10, [True] * 4)
		self.assertEqual(sum(fitted), 10)
		self.assertTrue(all(value % 0.25 == 0 and value >= 0.25 for value in fitted))
		self.assertEqual(len(fitted), 4)
		self.assertGreater(fitted[1], fitted[0])

	def test_scaling_down_works_as_well_as_up(self):
		fitted = self.fit([3, 3, 3], 6, [True] * 3)
		self.assertEqual(fitted, [2.0, 2.0, 2.0])

	def test_user_stated_hours_are_never_scaled(self):
		fitted = self.fit([0.5, 1, 1, 1], 8.5, [False, True, True, True])
		self.assertEqual(fitted[0], 0.5)
		self.assertEqual(sum(fitted), 8.5)

	def test_a_mismatch_without_estimates_still_fails_and_names_the_flag(self):
		with self.assertRaisesRegex(ts_common.SuiteError, '"estimated": true'):
			self.fit([1, 1], 3, [False, False])

	def test_fixed_hours_that_cannot_leave_room_raise(self):
		with self.assertRaisesRegex(ts_common.SuiteError, "too little"):
			self.fit([4, 1, 1], 4, [False, True, True])

	def test_estimated_cannot_be_mixed_with_missing_hours(self):
		with self.assertRaisesRegex(ts_common.SuiteError, "give every entry hours"):
			ts.resolve_hours([entry(hours=None), entry(hours=1, estimated=True)], 5)

	def test_build_warns_for_each_scaled_entry(self):
		doc, warnings = ts.build_timesheet(
			spec([entry(hours=1, estimated=True), entry(hours=1, estimated=True)], target_total_hours=3),
			PROFILE, ACTIVITY_TYPES, PROJECTS,
		)
		self.assertEqual(doc["total_hours"], 3)
		self.assertTrue(any("estimated 1h scaled to" in warning for warning in warnings))


class SundayWarningTests(unittest.TestCase):
	def warnings(self, date):
		return ts.build_timesheet(spec([entry()], date=date), PROFILE, ACTIVITY_TYPES, PROJECTS)[1]

	def test_a_sunday_is_flagged_before_anything_is_posted(self):
		self.assertTrue(any("Sunday" in warning for warning in self.warnings("2026-10-18")))

	def test_other_days_are_not(self):
		for date in ("2026-10-17", "2026-10-19"):
			self.assertFalse(any("Sunday" in warning for warning in self.warnings(date)))



class ScheduleTests(unittest.TestCase):
	def test_rows_run_back_to_back_and_roll_past_midnight(self):
		self.assertEqual(
			ts.schedule("2026-09-08", "23:00", [0.5, 1.25]),
			[
				("2026-09-08 23:00:00", "2026-09-08 23:30:00"),
				("2026-09-08 23:30:00", "2026-09-09 00:45:00"),
			],
		)


class BuildTests(unittest.TestCase):
	def build(self, entries, **overrides):
		return ts.build_timesheet(spec(entries, **overrides), PROFILE, ACTIVITY_TYPES, PROJECTS)

	def test_builds_a_draft_with_scheduled_rows(self):
		doc, warnings = self.build(
			[
				entry(hours=1.5, links=[{"label": "PR-1", "url": "https://example.com/pr/1"}]),
				entry(label="Coordination", activity_type="Communication", hours=0.5),
			]
		)
		self.assertEqual(warnings, [])
		self.assertEqual((doc["docstatus"], doc["status"], doc["title"]), (0, "Draft", "Example Employee"))
		self.assertEqual((doc["start_date"], doc["end_date"], doc["total_hours"]), ("2026-09-08", "2026-09-08", 2.0))
		first, second = doc["time_logs"]
		self.assertEqual((first["from_time"], first["to_time"]), ("2026-09-08 09:30:00", "2026-09-08 11:00:00"))
		self.assertEqual(second["from_time"], first["to_time"])
		self.assertEqual(first["description"], "Did the thing properly.\n\nRef: https://example.com/pr/1")
		self.assertEqual((first["project"], first["project_name"]), ("PROJ-0019", "Example Project"))
		self.assertEqual(second["activity_type"], "Communication")
		self.assertTrue(doc["note"].endswith("Total hours logged: 2h."))

	def test_spec_overrides_start_time_and_project(self):
		doc, _ = self.build([entry(project="Acme Rollout")], start_time="10:00")
		row = doc["time_logs"][0]
		self.assertEqual(row["from_time"], "2026-09-08 10:00:00")
		self.assertEqual(row["project_name"], "ACME")

	def test_invalid_activity_suggests_the_stored_casing(self):
		with self.assertRaisesRegex(ts_common.SuiteError, "'Code review'"):
			self.build([entry(activity_type="Code Review")])

	def test_project_warnings_are_deduplicated(self):
		_, warnings = self.build([entry(project="Acme Phase 2"), entry(project="Acme Phase 2"), entry(project="NOPE")])
		self.assertEqual(len(warnings), 2)
		self.assertIn("Completed", warnings[0])
		self.assertIn("isn't in the cached open projects", warnings[1])

	def test_stale_total_in_the_note_is_replaced(self):
		doc, _ = self.build([entry(hours=3)], note="Busy day. Total hours logged: 9h.")
		self.assertEqual(doc["note"], "Busy day. Total hours logged: 3h.")

	def test_split_hours_are_flagged(self):
		doc, warnings = self.build([entry(hours=None), entry(hours=None)], target_total_hours=3)
		self.assertEqual([row["hours"] for row in doc["time_logs"]], [1.5, 1.5])
		self.assertEqual(len(warnings), 2)

	def test_empty_spec_and_bad_date_raise(self):
		with self.assertRaisesRegex(ts_common.SuiteError, "no entries"):
			self.build([])
		with self.assertRaisesRegex(ts_common.SuiteError, "YYYY-MM-DD"):
			self.build([entry()], date="08/09/2026")


class BuildCommandTests(TempHome):
	def test_build_writes_both_files(self):
		ts_profile.save_profile(PROFILE)
		out = self.home / "out"
		spec_path = self.home / "spec.json"
		spec_path.write_text(json.dumps(spec([entry(hours=1.5)])))
		with contextlib.redirect_stdout(io.StringIO()):
			self.assertEqual(ts.main(["build", str(spec_path), "--out-dir", str(out)]), 0)
		doc = json.loads((out / "timesheet_2026-09-08.json").read_text())
		self.assertEqual(doc["total_hours"], 1.5)
		discord = (out / "discord_2026-09-08.md").read_text()
		self.assertTrue(discord.startswith("Today's (Sep 8) Update:\n1. Coding: Did the thing (1.5h)"))

	def test_build_reports_errors_without_a_traceback(self):
		ts_profile.save_profile(PROFILE)
		ts_catalogue.write_catalogue(
			PROFILE["site"],
			{"activity_types": sorted(ACTIVITY_TYPES), "projects": [], "currency": "INR"},
			dt.datetime.now(dt.timezone.utc),
		)
		spec_path = self.home / "spec.json"
		spec_path.write_text(json.dumps(spec([entry(activity_type="Nope")])))
		stderr = io.StringIO()
		with contextlib.redirect_stderr(stderr):
			self.assertEqual(ts.main(["build", str(spec_path), "--out-dir", str(self.home)]), 1)
		self.assertIn("not a valid Activity Type", stderr.getvalue())


class GitHubHelperTests(unittest.TestCase):
	def test_day_window_follows_the_utc_offset(self):
		window = ts_common.day_window("2026-09-08", "+05:30")
		self.assertEqual(window[0].isoformat(), "2026-09-08T00:00:00+05:30")
		self.assertTrue(ts_common.in_window("2026-09-08T18:20:00Z", window))
		self.assertFalse(ts_common.in_window("2026-09-08T18:40:00Z", window))

	def test_offset_must_be_well_formed(self):
		with self.assertRaisesRegex(ts_common.SuiteError, "UTC offset"):
			ts_common.parse_offset("5:30")

	def test_clean_text_drops_templates_checkboxes_and_trailers(self):
		body = "<!-- template -->\n## Summary\nFixes the **thing** and `__init__`\n- [x] tests added\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\nCo-Authored-By: bot <x@y>"
		self.assertEqual(ts_common.clean_text(body), "Summary Fixes the thing and __init__ - tests added")
		self.assertTrue(ts_common.clean_text("word " * 200, limit=50).endswith("…"))

	def test_github_client_needs_a_token(self):
		with mock.patch.dict(os.environ, {}, clear=True):
			with self.assertRaisesRegex(ts_common.SuiteError, "GITHUB_TOKEN"):
				ts.GitHubClient.from_env()


def search_item(repo, number, title, **extra):
	return {"repository_url": f"https://api.github.com/repos/{repo}", "number": number, "title": title,
			"html_url": f"https://github.com/{repo}/pull/{number}", "state": "closed", "created_at": "2026-09-08T05:00:00Z",
			"body": "PR body", "user": {"login": extra.pop("author", "someone")}, **extra}


def commit_item(repo, sha, message, date, author_login=None, author_name=None):
	return {"repository": {"full_name": repo}, "sha": sha, "html_url": f"https://github.com/{repo}/commit/{sha}",
			"author": {"login": author_login} if author_login else None,
			"commit": {"message": message, "author": {"date": date, "name": author_name or author_login}}}


class FakeGitHub:
	def __init__(self):
		self.searches = []
		self.pulls, self.review_lists, self.event_lists, self.compares = {}, {}, {}, {}
		self.fail = set()

	def search(self, kind, query):
		if any(marker in query for marker in self.fail):
			raise ts_common.SuiteError("The listed users cannot be searched")
		for search_kind, marker, items in self.searches:
			if search_kind == kind and marker in query:
				return items, len(items)
		return [], 0

	def pull(self, repo, number):
		return self.pulls[(repo, number)]

	def reviews(self, repo, number):
		return self.review_lists.get((repo, number), [])

	def events(self, user):
		return self.event_lists.get(user, [])

	def compare(self, repo, base, head):
		return self.compares[(repo, base, head)]

	def commit(self, repo, sha):
		raise AssertionError("not expected")


class GitHubDigestTests(unittest.TestCase):
	def fake(self):
		gh = FakeGitHub()
		gh.searches = [
			("commits", "author:amankumarui ", [commit_item("Org/app", "aaaaaaa1", "fix: thing\n\nbody text", "2026-09-08T10:00:00+05:30", "amankumarui")]),
			("commits", "author:maskeddefender ", [commit_item("Org/app", "bbbbbbb2", "fix: thing", "2026-09-08T10:05:00+05:30", None, "maskeddefender")]),
			("issues", "author:amankumarui created", [search_item("Org/app", 5, "fix: thing", pull_request={"merged_at": "2026-09-08T06:00:00Z"}, author="amankumarui")]),
			("issues", "reviewed-by:amankumarui", [search_item("Org/app", 7, "feat: teammate", author="teammate")]),
			("issues", "org:Org merged", [search_item("Org/app", 5, "fix: thing"), search_item("Org/app", 6, "feat: other")]),
		]
		gh.pulls = {
			("Org/app", 5): {"title": "fix: thing", "html_url": "u5", "user": {"login": "amankumarui"}, "merged_by": {"login": "amankumarui"}, "merged_at": "2026-09-08T06:00:00Z", "body": "b"},
			("Org/app", 6): {"title": "feat: other", "html_url": "u6", "user": {"login": "teammate"}, "merged_by": {"login": "lead"}, "merged_at": "2026-09-08T07:00:00Z", "body": "b"},
		}
		gh.review_lists = {("Org/app", 7): [
			{"user": {"login": "amankumarui"}, "state": "APPROVED", "submitted_at": "2026-09-08T09:00:00Z"},
			{"user": {"login": "amankumarui"}, "state": "COMMENTED", "submitted_at": "2026-09-10T09:00:00Z"},
		]}
		gh.event_lists = {"amankumarui": [
			{"type": "PushEvent", "created_at": "2026-09-08T08:00:00Z", "repo": {"name": "Other/core"}, "payload": {"before": "b" * 40, "head": "h" * 40}},
			{"type": "PushEvent", "created_at": "2026-09-01T08:00:00Z", "repo": {"name": "Other/core"}, "payload": {"before": "x" * 40, "head": "y" * 40}},
		]}
		gh.compares = {("Other/core", "b" * 40, "h" * 40): [
			commit_item("Other/core", "ccccccc3", "fix: branch-only work", "2026-09-08T13:00:00+05:30", None, "maskeddefender"),
			commit_item("Other/core", "ddddddd4", "chore: teammate", "2026-09-08T13:10:00+05:30", "teammate"),
		]}
		return gh

	def test_collects_the_day_and_merges_duplicate_identities(self):
		digest = ts.github_digest(self.fake(), "amankumarui, maskeddefender", "2026-09-08", "+05:30", "Org")
		titles = {(c["repo"], c["title"]): c for c in digest["commits"]}
		self.assertEqual(sorted(titles), [("Org/app", "fix: thing"), ("Other/core", "fix: branch-only work")])
		self.assertEqual(titles[("Org/app", "fix: thing")]["shas"], ["aaaaaaa", "bbbbbbb"])
		self.assertEqual(titles[("Org/app", "fix: thing")]["details"], "body text")
		self.assertEqual([(p["number"], p["merged"]) for p in digest["prs_raised"]], [(5, True)])
		self.assertEqual([p["number"] for p in digest["prs_merged"]], [5])
		self.assertEqual([(r["number"], r["states"]) for r in digest["reviews"]], [(7, ["APPROVED"])])
		self.assertEqual(digest["errors"], [])

	def test_orgs_default_to_the_repos_touched_that_day(self):
		digest = ts.github_digest(self.fake(), ["amankumarui", "maskeddefender"], "2026-09-08")
		self.assertEqual(digest["orgs"], ["Org", "Other"])

	def test_a_failing_search_becomes_a_warning(self):
		gh = self.fake()
		gh.fail = {"author:maskeddefender "}
		digest = ts.github_digest(gh, ["amankumarui", "maskeddefender"], "2026-09-08", orgs=["Org"])
		self.assertTrue(any("commits for maskeddefender" in e for e in digest["errors"]))
		self.assertEqual(len(digest["prs_merged"]), 1)

	def test_warns_when_the_activity_feed_does_not_reach_the_date(self):
		gh = self.fake()
		gh.event_lists["amankumarui"] = [gh.event_lists["amankumarui"][0]]
		digest = ts.github_digest(gh, ["amankumarui"], "2026-09-01", orgs=["Org"])
		self.assertTrue(any("activity feed" in e for e in digest["errors"]))

	def test_profile_keeps_github_usernames_but_validates_the_offset(self):
		with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"TIMESHEET_SUITE_HOME": home}):
			ts_profile.save_profile({**PROFILE, "github_users": "amankumarui,maskeddefender", "utc_offset": "+05:30"})
			self.assertEqual(ts_common.split_list(ts_profile.load_profile()["github_users"]), ["amankumarui", "maskeddefender"])
			with self.assertRaisesRegex(ts_common.SuiteError, "UTC offset"):
				ts_profile.save_profile({"utc_offset": "IST"})


JIRA_SITE = "https://example-co.atlassian.net"


def jira_digest(**ticket):
	base = {"key": "BILL-101", "summary": "Export invoices as CSV", "status": "In Review", "reasons": ["listed"], "prs": []}
	return {"version": 1, "date": "2026-09-08", "site": JIRA_SITE, "tickets": [{**base, **ticket}]}


def cache_catalogue(**overrides):
	values = dict(
		activity_types=set(ACTIVITY_TYPES), projects=dict(PROJECTS), fetched_at="2026-10-01T10:00:00Z",
		counts={"activity_types": len(ACTIVITY_TYPES), "projects": len(PROJECTS)}, currency="USD", source="cache",
	)
	values.update(overrides)
	return ts_catalogue.Catalogue(**values)


class BuildAllTests(unittest.TestCase):
	def run_build(self, entries, *, catalogue=cache_catalogue(), digest=None, targets=("discord",), profile=PROFILE, **overrides):
		return ts.build_all(spec(entries, **overrides), profile, catalogue=catalogue, digest=digest, targets=list(targets))

	def test_a_resolved_ticket_reaches_the_json_row_and_every_chat_message(self):
		result = self.run_build(
			[entry(tickets=["BILL-101"], summary="Built the export")],
			digest=jira_digest(), targets=("discord", "slack", "whatsapp"),
		)
		row = result.doc["time_logs"][0]["description"]
		self.assertIn("Jira: BILL-101", row)
		self.assertIn(f"Ref: {JIRA_SITE}/browse/BILL-101", row)
		self.assertEqual(sorted(result.rendered), ["discord", "slack", "whatsapp"])
		for target, rendered in result.rendered.items():
			with self.subTest(target):
				self.assertIn("BILL-101", rendered.files["md" if target == "discord" else "txt"])
				self.assertIn(f"{JIRA_SITE}/browse/BILL-101", rendered.files["md" if target == "discord" else "txt"])

	def test_the_spec_is_not_mutated_by_ticket_resolution(self):
		original = spec([entry(tickets=["BILL-101"])])
		before = json.dumps(original, sort_keys=True)
		ts.build_all(original, PROFILE, catalogue=cache_catalogue(), digest=jira_digest(), targets=["discord"])
		self.assertEqual(json.dumps(original, sort_keys=True), before)

	def test_a_catalogue_without_activity_types_skips_validation_and_warns_exactly_once(self):
		result = self.run_build(
			[entry(activity_type="Anything the site has"), entry(activity_type="Another", project="PROJ-9999")],
			catalogue=ts_catalogue.Catalogue(),
		)
		self.assertEqual(result.warnings.count(ts_catalogue.UNVALIDATED_WARNING), 1)
		self.assertEqual([row["activity_type"] for row in result.doc["time_logs"]], ["Anything the site has", "Another"])
		self.assertFalse(any("PROJ-9999" in warning for warning in result.warnings))

	def test_a_validated_catalogue_still_rejects_an_unknown_activity_type(self):
		with self.assertRaisesRegex(ts_common.SuiteError, "not a valid Activity Type"):
			self.run_build([entry(activity_type="Nope")], catalogue=cache_catalogue())

	def test_unknown_project_warning_says_it_may_be_completed_or_another_companys(self):
		cached = self.run_build([entry(project="PROJ-9999")], catalogue=cache_catalogue())
		self.assertTrue(any("cached open projects" in warning for warning in cached.warnings))

	def test_currency_comes_from_the_cache_else_inr_with_one_warning(self):
		self.assertEqual(self.run_build([entry()], catalogue=cache_catalogue(currency="USD")).doc["currency"], "USD")
		unknown = self.run_build([entry()], catalogue=cache_catalogue(currency=None))
		self.assertEqual(unknown.doc["currency"], "INR")
		self.assertEqual(sum("currency" in warning for warning in unknown.warnings), 1)

	def test_overflow_is_reported_for_every_failing_target_and_the_timesheet_survives(self):
		entries = [entry(summary="y" * 1500) for _ in range(3)]
		result = self.run_build(entries, targets=("discord", "slack", "teams", "whatsapp"))
		self.assertEqual(result.rendered, {})
		for name in ("Discord", "Slack", "WhatsApp"):
			self.assertIn(name, result.chat_error)
		self.assertNotIn("Teams", result.chat_error)
		self.assertEqual(result.doc["total_hours"], 3.0)

	def test_no_targets_renders_nothing(self):
		for targets in (None, []):
			result = self.run_build([entry()], targets=targets or ())
			self.assertEqual((result.rendered, result.chat_error), ({}, None))


class BuildChatExitCodeTests(TempHome):
	def build(self, entries=None, *flags, profile=None):
		ts_profile.save_profile(profile if profile is not None else PROFILE)
		out = self.home / "out"
		spec_path = self.home / "spec.json"
		spec_path.write_text(json.dumps(spec(entries or [entry(hours=1.5)])))
		stdout, stderr = io.StringIO(), io.StringIO()
		with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
			code = ts.main(["build", str(spec_path), "--out-dir", str(out), *flags])
		return code, stdout.getvalue(), stderr.getvalue(), out

	def never_asked(self):
		return {key: value for key, value in PROFILE.items() if key != "chat_targets"}

	def test_never_asked_writes_the_json_skips_chat_and_exits_2_with_the_question(self):
		code, stdout, _, out = self.build(None, profile=self.never_asked())
		self.assertEqual(code, 2)
		self.assertTrue((out / "timesheet_2026-09-08.json").exists())
		self.assertEqual([path.name for path in out.iterdir()], ["timesheet_2026-09-08.json"])
		self.assertIn("ask which chat apps", stdout)

	def test_an_override_answers_the_question_for_one_run_without_saving_it(self):
		code, _, _, out = self.build(None, "--chat-targets", "slack", profile=self.never_asked())
		self.assertEqual(code, 0)
		self.assertTrue((out / "chat_slack_2026-09-08.txt").exists())
		self.assertIsNone(ts_profile.read_profile().get("chat_targets"))

	def test_an_empty_saved_list_means_json_only_and_exit_0(self):
		code, stdout, _, out = self.build(None, profile={**PROFILE, "chat_targets": []})
		self.assertEqual(code, 0)
		self.assertEqual([path.name for path in out.iterdir()], ["timesheet_2026-09-08.json"])
		self.assertIn("no chat targets saved", stdout)

	def test_none_overrides_a_saved_list_for_one_run(self):
		code, _, _, out = self.build(None, "--chat-targets", "none")
		self.assertEqual(code, 0)
		self.assertEqual([path.name for path in out.iterdir()], ["timesheet_2026-09-08.json"])

	def test_overflow_keeps_the_json_writes_no_chat_file_and_exits_1_listing_every_target(self):
		code, _, stderr, out = self.build(
			[entry(summary="y" * 1500) for _ in range(3)], "--chat-targets", "discord,slack,teams"
		)
		self.assertEqual(code, 1)
		self.assertEqual([path.name for path in out.iterdir()], ["timesheet_2026-09-08.json"])
		self.assertIn("Discord", stderr)
		self.assertIn("Slack", stderr)
		self.assertNotIn("Teams update", stderr)

	def test_each_target_gets_a_status_line_with_size_limit_and_links(self):
		link = {"label": "PR-1", "url": "https://example.com/pr/1"}
		code, stdout, _, out = self.build([entry(links=[link])], "--chat-targets", "discord,gmail")
		self.assertEqual(code, 0)
		self.assertRegex(stdout, r"discord: discord_2026-09-08\.md · \d+/2000 chars · links embedded 1/1")
		self.assertRegex(stdout, r"gmail: chat_gmail_2026-09-08\.html, chat_gmail_2026-09-08\.txt.* · \d+/100000 bytes · links embedded 1/1")
		self.assertTrue((out / "discord_2026-09-08.md").exists())

	def test_a_jira_digest_next_to_the_outputs_is_picked_up_automatically(self):
		out = self.home / "out"
		out.mkdir()
		(out / "jira_2026-09-08.json").write_text(json.dumps(jira_digest()))
		code, _, _, out = self.build([entry(tickets=["BILL-101"])])
		self.assertEqual(code, 0)
		row = json.loads((out / "timesheet_2026-09-08.json").read_text())["time_logs"][0]["description"]
		self.assertIn("Jira: BILL-101 — Export invoices as CSV", row)

	def test_an_explicit_digest_path_wins_and_a_bad_one_is_an_error(self):
		digest_path = self.home / "elsewhere.json"
		digest_path.write_text(json.dumps(jira_digest()))
		code, _, _, out = self.build([entry(tickets=["BILL-101"])], "--jira-digest", str(digest_path))
		self.assertEqual(code, 0)
		self.assertIn("BILL-101", (out / "discord_2026-09-08.md").read_text())
		digest_path.write_text(json.dumps({"version": 9, "tickets": []}))
		code, _, stderr, _ = self.build([entry(tickets=["BILL-101"])], "--jira-digest", str(digest_path))
		self.assertEqual(code, 1)
		self.assertIn("Jira digest", stderr)

	def test_a_missing_profile_exits_2_like_profile_show(self):
		spec_path = self.home / "spec.json"
		spec_path.write_text(json.dumps(spec([entry()])))
		with contextlib.redirect_stderr(io.StringIO()):
			self.assertEqual(ts.main(["build", str(spec_path)]), 2)


class MainParserTests(unittest.TestCase):
	def test_every_command_is_registered_and_abbreviations_are_refused(self):
		parser, handlers = ts.build_parser()
		self.assertEqual(
			sorted(handlers),
			[
				"amend", "build", "cancel", "catalogue", "github", "jira", "post", "profile", "pull", "sessions", "submit",
				"sync", "update",
			],
		)
		for argv in (["bui", "spec.json"], ["build", "spec.json", "--out", "x"], ["submit", "TS-1", "--confirm", "TS-1"]):
			with self.subTest(argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
				parser.parse_args(argv)


class GitHubBranchTests(unittest.TestCase):
	def merged_digest(self, head):
		gh = GitHubDigestTests().fake()
		for pull in gh.pulls.values():
			pull.pop("head", None)
		if head is not None:
			gh.pulls[("Org/app", 5)]["head"] = head
		return ts.github_digest(gh, ["amankumarui"], "2026-09-08", orgs=["Org"])

	def test_merged_prs_carry_their_branch_name(self):
		digest = self.merged_digest({"ref": "feature/BILL-101-invoice-export"})
		self.assertEqual({pr["number"]: pr["branch"] for pr in digest["prs_merged"]}[5], "feature/BILL-101-invoice-export")

	def test_a_missing_or_null_head_gives_no_branch_instead_of_an_error(self):
		for head in (None, {}, {"ref": None}):
			with self.subTest(head=head):
				digest = self.merged_digest(head)
				self.assertTrue(digest["prs_merged"])
				self.assertTrue(all(pr["branch"] is None for pr in digest["prs_merged"]))


class _Raising:
	def __init__(self, error):
		self.error = error

	def open(self, *_args, **_kwargs):
		raise self.error


class GitHubClientHardeningTests(unittest.TestCase):
	def client(self, opener):
		client = ts.GitHubClient("tok-for-tests-123")
		client.opener = opener
		return client

	def test_a_token_with_control_characters_is_refused_without_echoing_it(self):
		with self.assertRaises(ts_common.SuiteError) as caught:
			ts.GitHubClient("ghp_abc\ndef")
		self.assertNotIn("abc", str(caught.exception))

	def test_a_surrounding_newline_in_the_token_is_stripped_not_sent(self):
		self.assertEqual(ts.GitHubClient("tok-for-tests-123\n").headers["Authorization"], "Bearer tok-for-tests-123")

	def test_a_value_error_from_the_request_becomes_a_suite_error_that_does_not_echo(self):
		client = self.client(_Raising(ValueError("Invalid header value b'Bearer tok-for-tests-123'")))
		with self.assertRaises(ts_common.SuiteError) as caught:
			client.get("/user")
		self.assertNotIn("tok-for-tests-123", str(caught.exception))

	def http_error(self, message):
		import urllib.error
		body = io.BytesIO(json.dumps({"message": message}).encode())
		return urllib.error.HTTPError("https://api.github.com/x", 403, "Forbidden", {}, body)

	def test_error_detail_is_cleaned_capped_and_redacted(self):
		long = self.client(_Raising(self.http_error("bad\x1b[31m thing " + "x" * 500)))
		with self.assertRaises(ts_common.SuiteError) as caught:
			long.get("/user")
		message = str(caught.exception)
		self.assertNotIn("\x1b", message)
		self.assertLess(len(message), 300)
		with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "sentinel-token-987654"}):
			leaky = self.client(_Raising(self.http_error("rejected sentinel-token-987654")))
			with self.assertRaises(ts_common.SuiteError) as caught:
				leaky.get("/user")
		self.assertNotIn("sentinel-token", str(caught.exception))
		self.assertIn("403", str(caught.exception))


class MainFailureTests(TempHome):
	def run_with(self, error, *argv):
		stdout, stderr = io.StringIO(), io.StringIO()
		with mock.patch.object(ts_profile, "read_profile", side_effect=error), \
				contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
			code = ts.main(list(argv) or ["profile", "show"])
		return code, stderr.getvalue()

	def test_an_os_error_is_a_short_message_with_exit_1_and_no_traceback(self):
		code, stderr = self.run_with(PermissionError(13, "Permission denied", "/secret/path/with/token-abc"))
		self.assertEqual(code, 1)
		self.assertTrue(stderr.startswith("error: "))
		self.assertNotIn("Traceback", stderr)
		self.assertNotIn("token-abc", stderr)

	def test_an_unexpected_exception_never_prints_its_text_or_a_traceback(self):
		code, stderr = self.run_with(KeyError("sentinel-secret-value"))
		self.assertEqual(code, 1)
		self.assertIn("unexpected KeyError", stderr)
		self.assertNotIn("sentinel-secret-value", stderr)
		self.assertNotIn("Traceback", stderr)

	def test_ctrl_c_exits_130_quietly(self):
		code, stderr = self.run_with(KeyboardInterrupt())
		self.assertEqual(code, 130)
		self.assertNotIn("Traceback", stderr)


class OutputPermissionTests(TempHome):
	def test_build_and_github_outputs_are_owner_only_but_the_chosen_folder_keeps_its_mode(self):
		import stat
		ts_profile.save_profile(PROFILE)
		out = self.home / "shared"
		out.mkdir(mode=0o755)
		out.chmod(0o755)
		spec_path = self.home / "spec.json"
		spec_path.write_text(json.dumps(spec([entry()])))
		with contextlib.redirect_stdout(io.StringIO()):
			self.assertEqual(ts.main(["build", str(spec_path), "--out-dir", str(out)]), 0)
		self.assertEqual(stat.S_IMODE((out / "timesheet_2026-09-08.json").stat().st_mode), 0o600)
		self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o755)


if __name__ == "__main__":
	unittest.main()
