"""Unit tests for ts_catalogue.py. Run from the skill folder:

    python3 -m unittest discover -s scripts -p 'test_ts_catalogue*.py' -v
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import stat
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ts_catalogue  # noqa: E402
from ts_common import Env, SuiteError, normalise_site, site_slug  # noqa: E402
from ts_fakes import FakeClient  # noqa: E402
from ts_testkit import TempHome  # noqa: E402

SITE = normalise_site("erp.example.com")
OTHER_SITE = normalise_site("https://erp.other.example")
NOW = dt.datetime(2026, 10, 1, 10, 0, 0, tzinfo=dt.timezone.utc)

RECORDS = {
	"Activity Type": [
		{"name": "Coding", "disabled": 0},
		{"name": "Site Visit ", "disabled": 0},  # trailing space is part of the Link value
		{"name": "Old Thing", "disabled": 1},
	],
	# Frappe drops `company` for select-only users: the rows never carry it.
	"Project": [
		{"name": "PROJ-0001", "project_name": "Internal", "status": "Open"},
		{"name": "Acme, Phase 1", "project_name": "ACME-P1", "status": "Open"},
		{"name": "Done Deal", "project_name": "DD", "status": "Completed"},
	],
	"Company": [{"name": "Example Pvt Ltd", "default_currency": "USD"}],
}


def client(**overrides):
	return FakeClient(records={**RECORDS, **overrides})


def refreshed(site=SITE, fake=None, company="Example Pvt Ltd"):
	data = ts_catalogue.fetch_catalogue(fake or client(), company)
	return ts_catalogue.write_catalogue(site, data, NOW)


class FetchTests(TempHome):
	def test_queries_only_enabled_activity_types_and_open_projects_without_company(self):
		fake = client()
		ts_catalogue.fetch_catalogue(fake, "Example Pvt Ltd")
		calls = {call[1]: call for call in fake.calls if call[0] == "list_docs"}
		self.assertEqual(calls["Activity Type"][2], [["disabled", "=", 0]])
		self.assertEqual(calls["Project"][2], [["status", "=", "Open"]])
		self.assertNotIn("company", calls["Project"][3])
		self.assertEqual(calls["Company"][2], [["name", "=", "Example Pvt Ltd"]])

	def test_fetch_survives_project_rows_without_company_and_keeps_exact_names(self):
		data = ts_catalogue.fetch_catalogue(client(), "Example Pvt Ltd")
		self.assertEqual(data["activity_types"], ["Coding", "Site Visit "])
		self.assertEqual([row["name"] for row in data["projects"]], ["Acme, Phase 1", "PROJ-0001"])
		self.assertEqual(data["currency"], "USD")

	def test_company_lookup_failure_is_not_fatal(self):
		fake = client()
		real = fake.list_docs

		def flaky(doctype, *args, **kwargs):
			if doctype == "Company":
				raise SuiteError("403")
			return real(doctype, *args, **kwargs)

		fake.list_docs = flaky
		self.assertIsNone(ts_catalogue.fetch_catalogue(fake, "Example Pvt Ltd")["currency"])
		self.assertIsNone(ts_catalogue.fetch_catalogue(client(), None)["currency"])

	def test_empty_activity_type_list_aborts(self):
		with self.assertRaisesRegex(SuiteError, "Activity Type.*empty"):
			ts_catalogue.fetch_catalogue(client(**{"Activity Type": []}), "Example Pvt Ltd")


class CacheTests(TempHome):
	def test_refresh_writes_the_site_scoped_layout_privately(self):
		folder = refreshed()
		self.assertEqual(folder, self.home / "catalogues" / site_slug(SITE))
		self.assertEqual(sorted(path.name for path in folder.iterdir()), ["activity_types.csv", "catalogue.json", "projects.csv"])
		meta = json.loads((folder / "catalogue.json").read_text())
		self.assertEqual(
			meta,
			{
				"schema": 1,
				"site": SITE,
				"fetched_at": "2026-10-01T10:00:00Z",
				"counts": {"activity_types": 2, "projects": 2},
				"currency": "USD",
			},
		)
		self.assertEqual(stat.S_IMODE(folder.stat().st_mode), 0o700)
		for path in folder.iterdir():
			self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600, path.name)

	def test_cache_files_round_trip_through_the_loaders(self):
		folder = refreshed()
		self.assertEqual(ts_catalogue.load_activity_types(folder / "activity_types.csv"), {"Coding", "Site Visit "})
		self.assertEqual(
			ts_catalogue.load_projects(folder / "projects.csv"),
			{
				"PROJ-0001": {"short_code": "Internal", "status": "Open", "company": ""},
				"Acme, Phase 1": {"short_code": "ACME-P1", "status": "Open", "company": ""},
			},
		)

	def test_read_round_trips_what_was_written(self):
		refreshed()
		cached = ts_catalogue.read_catalogue(SITE)
		self.assertEqual(cached.source, "cache")
		self.assertEqual(cached.activity_types, {"Coding", "Site Visit "})
		self.assertEqual(set(cached.projects), {"PROJ-0001", "Acme, Phase 1"})
		self.assertEqual((cached.fetched_at, cached.currency), ("2026-10-01T10:00:00Z", "USD"))
		self.assertEqual(cached.counts, {"activity_types": 2, "projects": 2})

	def test_nothing_cached_reads_as_none_even_with_orphan_csvs(self):
		self.assertIsNone(ts_catalogue.read_catalogue(SITE))
		folder = refreshed()
		(folder / "catalogue.json").unlink()  # crash before the meta (written last) landed
		self.assertIsNone(ts_catalogue.read_catalogue(SITE))

	def test_interrupted_refresh_is_detected_by_the_meta_counts(self):
		folder = refreshed()
		bigger = client(**{"Activity Type": RECORDS["Activity Type"] + [{"name": "Extra", "disabled": 0}]})
		real = ts_catalogue.write_private_text

		def crash_on_projects(path, text):
			if Path(path).name == "projects.csv":
				raise OSError("disk full")
			real(path, text)

		with mock.patch.object(ts_catalogue, "write_private_text", crash_on_projects):
			with self.assertRaises(OSError):
				refreshed(fake=bigger)
		with self.assertRaisesRegex(SuiteError, "unreadable"):
			ts_catalogue.read_catalogue(SITE)
		self.assertTrue((folder / "catalogue.json").exists())

	def test_corrupt_cache_fails_closed(self):
		def damage_meta(folder):
			(folder / "catalogue.json").write_text("{not json")

		def drop_projects(folder):
			(folder / "projects.csv").unlink()

		def extra_row(folder):
			with (folder / "projects.csv").open("a") as handle:
				handle.write("Sneaky,SN,Open,\n")

		def newer_schema(folder):
			path = folder / "catalogue.json"
			path.write_text(json.dumps({**json.loads(path.read_text()), "schema": 2}))

		def bad_counts(folder):
			path = folder / "catalogue.json"
			path.write_text(json.dumps({**json.loads(path.read_text()), "counts": {"activity_types": "2"}}))

		for damage in (damage_meta, drop_projects, extra_row, newer_schema, bad_counts):
			with self.subTest(damage=damage.__name__):
				damage(refreshed())
				with self.assertRaisesRegex(SuiteError, "unreadable"):
					ts_catalogue.read_catalogue(SITE)
				with self.assertRaises(SuiteError):
					ts_catalogue.resolve_catalogue(SITE, {})
				refreshed()  # refresh is the remedy and repairs it
				self.assertEqual(ts_catalogue.read_catalogue(SITE).counts["projects"], 2)

	def test_failed_fetch_leaves_the_existing_cache_untouched(self):
		folder = refreshed()
		before = {path.name: path.read_bytes() for path in folder.iterdir()}
		with self.assertRaises(SuiteError):
			refreshed(fake=client(**{"Activity Type": []}))
		real = FakeClient.list_docs

		def project_outage(self, doctype, *args, **kwargs):
			if doctype == "Project":
				raise SuiteError("Frappe GET /api/resource/Project failed (503)")
			return real(self, doctype, *args, **kwargs)

		with mock.patch.object(FakeClient, "list_docs", project_outage):
			with self.assertRaises(SuiteError):
				refreshed()
		self.assertEqual({path.name: path.read_bytes() for path in folder.iterdir()}, before)

	def test_cache_whose_meta_names_another_site_is_ignored(self):
		folder = refreshed()
		path = folder / "catalogue.json"
		path.write_text(json.dumps({**json.loads(path.read_text()), "site": "http://erp.example.com"}))
		self.assertIsNone(ts_catalogue.read_catalogue(SITE))
		self.assertEqual(ts_catalogue.resolve_catalogue(SITE, {}).source, "none")


class ResolveTests(TempHome):
	def test_a_site_with_no_cache_has_nothing_to_validate_against(self):
		cat = ts_catalogue.resolve_catalogue(OTHER_SITE, {})
		self.assertEqual((cat.source, cat.activity_types), ("none", None))

	def test_other_sites_without_a_cache_skip_validation(self):
		cat = ts_catalogue.resolve_catalogue(SITE, {})
		self.assertEqual((cat.source, cat.activity_types, cat.projects, cat.currency), ("none", None, {}, None))
		self.assertIn("not validated", ts_catalogue.UNVALIDATED_WARNING)
		self.assertNotIn("\n", ts_catalogue.UNVALIDATED_WARNING)

	def test_caches_of_different_sites_do_not_mix(self):
		refreshed(site=SITE)
		self.assertEqual(ts_catalogue.resolve_catalogue(normalise_site("erp.other.org"), {}).source, "none")


def run(*argv, profile=None, fake=None, sites=None):
	"""Drive `catalogue ...` through the real argparse wiring; returns (exit code, output lines)."""
	root = argparse.ArgumentParser(allow_abbrev=False)
	handlers = ts_catalogue.add_parsers(root.add_subparsers(dest="command", required=True))
	lines: list[str] = []

	def client_factory(site):
		if sites is not None:
			sites.append(site)
		return fake or client()

	env = Env(load_profile=lambda: profile or {}, read_profile=lambda: profile, client_factory=client_factory, out=lines.append)
	args = root.parse_args(["catalogue", *argv])
	return handlers[args.command](args, env), lines


class CliTests(TempHome):
	PROFILE = {"site": SITE, "company": "Example Pvt Ltd"}

	def test_refresh_reports_counts_diff_and_writes_the_cache(self):
		sites: list[str] = []
		code, lines = run("refresh", profile=self.PROFILE, sites=sites)
		text = "\n".join(lines)
		self.assertEqual((code, sites), (0, [SITE]))
		self.assertIn(f"site: {SITE}", text)
		self.assertIn("activity types: 2 (+2 -0)", text)
		self.assertIn("projects: 2 (+2 -0)", text)
		self.assertIn("USD", text)
		_, again = run("refresh", profile=self.PROFILE, fake=client(**{"Activity Type": [{"name": "Coding", "disabled": 0}]}))
		self.assertIn("activity types: 1 (+0 -1)", "\n".join(again))
		self.assertEqual(ts_catalogue.read_catalogue(SITE).activity_types, {"Coding"})

	def test_refresh_without_any_site_is_a_setup_error(self):
		with self.assertRaises(SuiteError) as caught:
			run("refresh", profile={"company": "X"})
		self.assertEqual(caught.exception.exit_code, 2)

	def test_site_flag_is_accepted_only_for_first_run_or_the_stored_site(self):
		sites: list[str] = []
		code, _ = run("refresh", "--site", "erp.example.com/app/home", profile={}, sites=sites)  # first run
		self.assertEqual((code, sites), (0, [SITE]))
		run("refresh", "--site", "ERP.example.com", profile=self.PROFILE, sites=sites)  # same site, other spelling
		self.assertEqual(sites, [SITE, SITE])
		with self.assertRaisesRegex(SuiteError, "confirm-site-change"):
			run("refresh", "--site", "https://evil.example.net", profile=self.PROFILE, sites=sites)
		self.assertEqual(sites, [SITE, SITE])  # no client, hence no credentials, was ever created for it

	def test_refresh_repairs_a_corrupt_cache_instead_of_failing(self):
		(refreshed() / "catalogue.json").write_text("garbage")
		code, _ = run("refresh", profile=self.PROFILE)
		self.assertEqual(code, 0)
		self.assertEqual(ts_catalogue.read_catalogue(SITE).counts["activity_types"], 2)

	def test_list_header_states_source_date_and_counts_then_filters(self):
		refreshed()
		code, lines = run("list", "--type", "project", "--match", "acme", profile=self.PROFILE)
		self.assertEqual(code, 0)
		self.assertRegex(lines[0], r"source: cache erp\.example\.com \(refreshed 2026-10-01\).*2 activity types, 2 projects")
		body = "\n".join(lines[1:])
		self.assertIn("Acme, Phase 1", body)
		self.assertNotIn("PROJ-0001", body)
		self.assertNotIn("Coding", body)

	def test_list_without_type_shows_both_and_match_is_case_insensitive(self):
		refreshed()
		_, lines = run("list", "--match", "CODING", profile=self.PROFILE)
		self.assertEqual([line.strip() for line in lines[1:] if "Coding" in line], ["Coding"])

	def test_list_on_uncatalogued_site_says_nothing_is_validated(self):
		code, lines = run("list", profile=self.PROFILE)
		self.assertEqual(code, 0)
		self.assertRegex(lines[0], r"source: none")
		self.assertIn("catalogue refresh", "\n".join(lines))


	def test_abbreviated_flags_are_not_accepted(self):
		for argv in (["refresh", "--si", "x.com"], ["list", "--ty", "project"]):
			with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
				run(*argv, profile=self.PROFILE)


if __name__ == "__main__":
	unittest.main()
