"""Unit tests for ts_jira.py (fake transport / loopback servers only; no network). Run from the skill folder:

    python3 -m unittest discover -s scripts -p 'test_ts_jira*.py'
"""
from __future__ import annotations

import argparse
import base64
import copy
import http.server
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ts_common  # noqa: E402
import ts_jira  # noqa: E402
from ts_testkit import entry  # noqa: E402

SITE = "https://acme.atlassian.net"
TOKEN = "TOKEN-SECRET-123"
EMAIL = "me@example.com"
CREDS = ts_jira.JiraCredentials(site=SITE, email=EMAIL, token=TOKEN)


def issue(key, summary="Fix export", status="In Progress", updated="2026-09-08T10:00:00.000+0530", ident=None):
	return {
		"id": ident or str(10000 + int(key.split("-")[1])),
		"key": key,
		"fields": {
			"summary": summary,
			"status": {"name": status},
			"updated": updated,
			"assignee": {"accountId": "acct-1", "emailAddress": EMAIL, "displayName": "Example Employee"},
		},
	}


class Fake:
	"""Transport double: `handler(method, parts, body) -> (status, payload[, headers])`; records every call."""

	def __init__(self, handler):
		self.handler = handler
		self.calls = []

	def __call__(self, method, url, headers, body, timeout):
		parts = urllib.parse.urlsplit(url)
		parsed = json.loads(body) if body else None
		self.calls.append({"method": method, "url": url, "host": parts.hostname, "path": parts.path, "headers": dict(headers), "body": parsed})
		result = self.handler(method, parts, parsed)
		status, payload = result[0], result[1]
		raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
		return status, (result[2] if len(result) > 2 else {}), raw

	def paths(self):
		return [call["path"] for call in self.calls]


def jira_handler(issues=(), search=None, dev=None):
	by_key = {item["key"]: item for item in issues}

	def handle(method, parts, body):
		path = parts.path
		if path == "/rest/api/3/search/jql":
			return 200, {"issues": list(search if search is not None else issues), "isLast": True}
		if path == "/rest/api/3/myself":
			return 200, {"displayName": "Example Employee", "accountId": "acct-1", "emailAddress": EMAIL}
		if path.startswith("/rest/api/3/issue/"):
			found = by_key.get(path.rsplit("/", 1)[1])
			return (200, found) if found else (404, {"errorMessages": ["Issue does not exist"]})
		if path.startswith("/rest/dev-status/") and dev is not None:
			return dev(path, urllib.parse.parse_qs(parts.query))
		return 404, {}

	return handle


def client_for(handler, creds=CREDS):
	fake = Fake(handler)
	sleeps = []
	client = ts_jira.JiraClient(creds, transport=fake, sleep=sleeps.append)
	client.fake, client.sleeps = fake, sleeps
	return client


class ParsingTests(unittest.TestCase):
	def test_refs_from_titles_urls_and_branches_skip_false_positives(self):
		text = "ABC-123 fix, see feature/XYZ-9-pdf and bugfix-QA_2-77; PR-3647 UTF-8 SHA-256 CVE-2024-1234 abc-5 lower"
		self.assertEqual(ts_jira.parse_ticket_refs(text), ["ABC-123", "XYZ-9", "QA_2-77"])

	def test_refs_are_deduped_in_order(self):
		self.assertEqual(ts_jira.parse_ticket_refs("B-1 AB-2 AB-2 AA-1 AB-2"), ["AB-2", "AA-1"])

	def test_ticket_ref_accepts_keys_and_urls_and_reports_host(self):
		self.assertEqual(ts_jira.ticket_ref("abc-12"), ("ABC-12", None))
		self.assertEqual(ts_jira.ticket_ref("https://Acme.atlassian.net/browse/ABC-12?x=1"), ("ABC-12", "acme.atlassian.net"))
		self.assertEqual(
			ts_jira.ticket_ref("acme.atlassian.net/jira/software/projects/ABC/boards/1?selectedIssue=ABC-7"),
			("ABC-7", "acme.atlassian.net"),
		)

	def test_ticket_ref_rejects_junk_userinfo_and_never_echoes_it(self):
		for bad in ("hello", "https://acme.atlassian.net/", "ftp://acme.atlassian.net/browse/A-1", "ABC-0", ""):
			with self.assertRaises(ts_common.SuiteError, msg=bad):
				ts_jira.ticket_ref(bad)
		with self.assertRaises(ts_common.SuiteError) as caught:
			ts_jira.ticket_ref("https://me:hunter2pw@acme.atlassian.net/browse/ABC-1")
		self.assertNotIn("hunter2pw", str(caught.exception))

	def test_jira_line(self):
		self.assertEqual(ts_jira.jira_line("ABC-1", "PDF  export\nfails <b>", "In Review"), "Jira: ABC-1 — PDF export fails b [In Review]")
		self.assertEqual(ts_jira.jira_line("ABC-1"), "Jira: ABC-1")


class CredentialRoutingTests(unittest.TestCase):
	def resolve(self, *, site=None, email=None, profile=None, environ=None, hosts=()):
		return ts_jira.resolve_credentials(site=site, email=email, profile=profile or {}, environ=environ or {}, hosts=hosts)

	def test_site_and_email_precedence_flag_env_profile_token_only_from_env(self):
		profile = {"jira_site": "prof.atlassian.net", "jira_email": "prof@example.com", "jira_api_token": "nope"}
		environ = {"JIRA_SITE": "env.atlassian.net", "JIRA_EMAIL": "env@example.com", "JIRA_API_TOKEN": TOKEN}
		creds, missing, _ = self.resolve(site="flag.atlassian.net", email="flag@example.com", profile=profile, environ=environ)
		self.assertEqual((creds.site, creds.email, creds.token, missing), ("https://flag.atlassian.net", "flag@example.com", TOKEN, []))
		creds, _, _ = self.resolve(profile=profile, environ=environ)
		self.assertEqual((creds.site, creds.email), ("https://env.atlassian.net", "env@example.com"))
		creds, missing, _ = self.resolve(profile=profile, environ={})
		self.assertIsNone(creds)
		self.assertEqual(len(missing), 1)  # only the token: site and email come from the profile
		self.assertIn("JIRA_API_TOKEN", missing[0])

	def test_everything_missing_is_listed_at_once_and_pasted_url_is_only_a_candidate(self):
		creds, missing, candidate = self.resolve(hosts=("evil.atlassian.net",))
		self.assertIsNone(creds)
		self.assertEqual(len(missing), 3)
		self.assertEqual(candidate, "https://evil.atlassian.net")
		_, _, candidate = self.resolve(hosts=("evil.example",))
		self.assertIsNone(candidate)

	def test_pasted_url_host_must_equal_the_resolved_site(self):
		with self.assertRaises(ts_common.SuiteError):
			self.resolve(site="acme.atlassian.net", environ={"JIRA_API_TOKEN": TOKEN}, email=EMAIL, hosts=("other.atlassian.net",))
		creds, missing, _ = self.resolve(site="acme.atlassian.net", environ={"JIRA_API_TOKEN": TOKEN}, email=EMAIL, hosts=("acme.atlassian.net",))
		self.assertEqual((creds.site, missing), (SITE, []))

	def test_non_atlassian_site_and_email_with_token_are_rejected(self):
		with self.assertRaises(ts_common.SuiteError):
			self.resolve(site="https://evil.example", email=EMAIL, environ={"JIRA_API_TOKEN": TOKEN})
		with self.assertRaises(ts_common.SuiteError):
			self.resolve(site="acme.atlassian.net", email=f"{EMAIL}:{TOKEN}", environ={"JIRA_API_TOKEN": TOKEN})

	def test_client_refuses_a_non_atlassian_site(self):
		with self.assertRaises(ts_common.SuiteError):
			ts_jira.JiraClient(ts_jira.JiraCredentials(site="https://evil.example", email=EMAIL, token=TOKEN), transport=Fake(jira_handler()))


class ClientTests(unittest.TestCase):
	def test_basic_auth_goes_only_to_the_exact_site_host(self):
		client = client_for(jira_handler([issue("ABC-1")]))
		client.fetch_keys(["ABC-1"])
		client.myself()
		for call in client.fake.calls:
			self.assertEqual(call["host"], "acme.atlassian.net")
			self.assertEqual(call["headers"]["Authorization"], "Basic " + base64.b64encode(f"{EMAIL}:{TOKEN}".encode()).decode())
		with self.assertRaises(ts_common.SuiteError):
			client.request("GET", "//evil.example/x")
		self.assertEqual(len(client.fake.calls), 2)

	def test_search_pages_with_next_page_token_and_stops_on_repeat(self):
		pages = {None: ([issue("AB-1"), issue("AB-2")], "t1"), "t1": ([issue("AB-3")], "t2"), "t2": ([issue("AB-4")], "t2")}

		def handler(method, parts, body):
			issues, token = pages[body.get("nextPageToken")]
			return 200, {"issues": issues, "nextPageToken": token}

		client = client_for(handler)
		found, truncated = client.search("assignee = currentUser()")
		self.assertEqual([item["key"] for item in found], ["AB-1", "AB-2", "AB-3", "AB-4"])
		self.assertEqual(len(client.fake.calls), 3)  # the repeated token ended the loop
		self.assertFalse(truncated)

	def test_search_truncates_at_the_limit(self):
		client = client_for(lambda m, p, b: (200, {"issues": [issue(f"AB-{i}") for i in range(1, 4)], "nextPageToken": f"t{len(client.fake.calls)}"}))
		found, truncated = client.search("x", limit=5)
		self.assertEqual((len(found), truncated), (5, True))

	def test_429_honours_retry_after_then_gives_up(self):
		client = client_for(lambda m, p, b: (429, {}, {"Retry-After": "7"}))
		with self.assertRaises(ts_jira.JiraError) as caught:
			client.myself()
		self.assertEqual(caught.exception.status, 429)
		self.assertEqual(client.sleeps, [7, 7])
		slow = client_for(lambda m, p, b: (429, {}, {"retry-after": "9999"}))
		with self.assertRaises(ts_jira.JiraError):
			slow.myself()
		self.assertTrue(all(wait <= ts_jira.RETRY_CAP_S for wait in slow.sleeps))

	def test_5xx_is_retried_once_then_succeeds_or_fails(self):
		state = {"n": 0}

		def flaky(method, parts, body):
			state["n"] += 1
			return (502, {}) if state["n"] == 1 else (200, {"displayName": "X"})

		client = client_for(flaky)
		self.assertEqual(client.myself()["displayName"], "X")
		down = client_for(lambda m, p, b: (503, {}))
		with self.assertRaises(ts_jira.JiraError):
			down.myself()
		self.assertEqual(len(down.fake.calls), 2)

	def test_status_messages(self):
		cases = {
			401: f"Jira rejected the credentials for {SITE} (401). JIRA_EMAIL must be your Atlassian account email and JIRA_API_TOKEN a classic API token (id.atlassian.com/manage-profile/security/api-tokens), not a password or email:token pair.",
			403: "Jira refused access (403) — the account lacks Browse permission or the site blocks API tokens",
			404: f"No Jira Cloud site at {SITE} (404) — check the site name",
		}
		for status, message in cases.items():
			with self.assertRaises(ts_jira.JiraError, msg=status) as caught:
				client_for(lambda m, p, b, s=status: (s, {})).myself()
			self.assertEqual(str(caught.exception), message)
			self.assertEqual(caught.exception.status, status)

	def test_redirect_and_non_json_responses_are_errors(self):
		with self.assertRaises(ts_jira.JiraError):
			client_for(lambda m, p, b: (302, {}, {"Location": "https://evil.example/login"})).myself()
		with self.assertRaises(ts_jira.JiraError):
			client_for(lambda m, p, b: (200, b"<html>login</html>")).myself()

	def test_token_never_appears_in_errors_digest_or_output(self):
		auth = base64.b64encode(f"{EMAIL}:{TOKEN}".encode()).decode()
		leaks = [TOKEN, auth]
		echo = {"errorMessages": [f"bad credentials {TOKEN} for {EMAIL}: Basic {auth}"]}
		for status in (400, 401, 403, 404, 500):
			with self.assertRaises(ts_common.SuiteError, msg=status) as caught:
				client_for(lambda m, p, b, s=status: (s, echo)).request("GET", "/rest/api/3/issue/A-1")
			for leak in leaks:
				self.assertNotIn(leak, str(caught.exception))

		def unreachable(method, url, headers, body, timeout):
			raise OSError(f"connect failed with {headers['Authorization']} {TOKEN}")

		client = ts_jira.JiraClient(CREDS, transport=unreachable, sleep=lambda s: None)
		with self.assertRaises(ts_common.SuiteError) as caught:
			client.myself()
		for leak in leaks:
			self.assertNotIn(leak, str(caught.exception))
		# a per-key failure that echoes the secret lands in digest errors: redacted too
		client = client_for(lambda m, p, b: (400, echo))
		_, _, errors = client.fetch_keys(["ABC-1"])
		self.assertTrue(errors)
		for leak in leaks:
			self.assertNotIn(leak, json.dumps(errors))


class RedirectTransportTests(unittest.TestCase):
	def serve(self, handler):
		server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
		thread = threading.Thread(target=server.serve_forever, daemon=True)
		thread.start()
		self.addCleanup(server.server_close)
		self.addCleanup(server.shutdown)
		return server

	def test_default_transport_follows_no_redirect_and_never_forwards_credentials(self):
		hits = []

		class Target(http.server.BaseHTTPRequestHandler):
			def do_GET(self):
				hits.append(self.headers.get("Authorization"))
				self.send_response(200)
				self.end_headers()

			def log_message(self, *args):
				pass

		target = self.serve(Target)
		target_url = f"http://127.0.0.1:{target.server_port}/stolen"
		same = {"where": None}

		class Redirector(http.server.BaseHTTPRequestHandler):
			def do_GET(self):
				self.send_response(302)
				self.send_header("Location", same["where"] if self.path == "/same" else target_url)
				self.end_headers()

			def log_message(self, *args):
				pass

		origin = self.serve(Redirector)
		base = f"http://127.0.0.1:{origin.server_port}"
		same["where"] = base + "/elsewhere"
		transport = ts_jira.make_transport(base, (urllib.request.ProxyHandler({}),))
		for path in ("/other-origin", "/same"):
			with self.assertRaises(ts_common.SuiteError, msg=path):
				transport("GET", base + path, {"Authorization": "Basic secret"}, None, 5)
		self.assertEqual(hits, [])


class FetchTests(unittest.TestCase):
	def test_assigned_query_is_widened_then_cut_to_the_day_in_the_profile_offset(self):
		items = [
			issue("AB-1", updated="2026-09-08T23:30:00.000+0530"),
			issue("AB-2", updated="2026-09-09T00:10:00.000+0530"),
			issue("AB-3", updated="2026-09-07T23:59:00.000+0530"),
			issue("AB-4", updated="2026-09-08T00:00:00.000+0530"),
			issue("AB-5", updated="2026-09-08T20:00:00.000-0500"),
		]
		client = client_for(jira_handler(search=items))
		found, warnings = client.fetch_assigned("2026-09-08", "+05:30")
		self.assertEqual([item["key"] for item in found], ["AB-4", "AB-1"])  # oldest update first
		self.assertEqual(warnings, [])
		body = client.fake.calls[0]["body"]
		self.assertIn("assignee = currentUser()", body["jql"])
		self.assertIn('"2026-09-07 00:00"', body["jql"])
		self.assertIn('"2026-09-10 00:00"', body["jql"])
		self.assertNotIn("description", body["fields"])

	def test_keys_are_fetched_one_by_one_with_failures_isolated(self):
		def handler(method, parts, body):
			key = parts.path.rsplit("/", 1)[1]
			return {"AB-1": (200, issue("AB-1")), "AB-2": (404, {}), "AB-3": (403, {}), "AB-4": (503, {}), "AB-5": (200, issue("AB-5"))}[key]

		client = client_for(handler)
		found, missing, errors = client.fetch_keys(["AB-1", "AB-2", "AB-3", "AB-4", "AB-5", "AB-1"])
		self.assertEqual([item["key"] for item in found], ["AB-1", "AB-5"])
		self.assertEqual(missing, ["AB-2"])
		self.assertEqual(sorted(error.split(":")[0] for error in errors), ["AB-3", "AB-4"])
		self.assertEqual(client.fake.paths().count("/rest/api/3/issue/AB-1"), 1)

	def test_bad_credentials_abort_the_key_loop(self):
		client = client_for(lambda m, p, b: (401, {}))
		with self.assertRaises(ts_jira.JiraError):
			client.fetch_keys(["AB-1", "AB-2"])
		self.assertEqual(len(client.fake.calls), 1)

	def test_key_lookups_are_capped(self):
		client = client_for(lambda m, p, b: (404, {}))
		_, missing, errors = client.fetch_keys([f"AB-{n}" for n in range(1, ts_jira.MAX_KEY_LOOKUPS + 6)])
		self.assertEqual(len(client.fake.calls), ts_jira.MAX_KEY_LOOKUPS)
		self.assertEqual(len(missing), ts_jira.MAX_KEY_LOOKUPS)
		self.assertTrue(any("first" in error for error in errors))


GITHUB = {
	"commits": [{"repo": "Org/app", "title": "ABC-3 tidy imports", "details": "", "shas": ["aaaaaaa"], "urls": ["https://github.com/Org/app/commit/aaaaaaa"]}],
	"prs_raised": [{"repo": "Org/app", "number": 11, "title": "ABC-1 fix export (PR-3647 UTF-8)", "url": "https://github.com/Org/app/pull/11", "state": "closed", "description": ""}],
	"prs_merged": [{"repo": "Org/app", "number": 12, "title": "other work", "url": "https://github.com/Org/app/pull/12", "branch": "feature/ABC-2-pdf", "description": ""}],
	"reviews": [{"repo": "Org/app", "number": 13, "title": "ZZZ-9 not a ticket", "url": "https://github.com/Org/app/pull/13"}],
}


def full_handler(dev=None):
	return jira_handler([issue("ABC-1"), issue("ABC-2"), issue("ABC-3"), issue("ABC-9")], search=[issue("ABC-1")], dev=dev)


class DigestTests(unittest.TestCase):
	def digest(self, client, **kwargs):
		return ts_jira.build_digest(client, "2026-09-08", "+05:30", **kwargs)

	def test_one_ticket_in_two_sources_has_merged_reasons(self):
		client = client_for(full_handler())
		digest = self.digest(client, keys=["ABC-1"])
		self.assertEqual([item["key"] for item in digest["tickets"]], ["ABC-1"])
		self.assertEqual(digest["tickets"][0]["reasons"], ["assigned_updated", "listed"])
		self.assertEqual(digest["tickets"][0]["url"], f"{SITE}/browse/ABC-1")
		self.assertEqual(digest["site"], SITE)

	def test_missing_listed_key_is_reported(self):
		digest = self.digest(client_for(full_handler()), keys=["ABC-1", "ZZZ-404"])
		self.assertEqual(digest["missing_keys"], ["ZZZ-404"])
		self.assertTrue(any("ZZZ-404" in error for error in digest["errors"]))

	def test_github_keys_attach_prs_and_commits_and_fetch_unlisted_tickets(self):
		client = client_for(full_handler())
		digest = self.digest(client, github=GITHUB)
		by_key = {item["key"]: item for item in digest["tickets"]}
		self.assertEqual(sorted(by_key), ["ABC-1", "ABC-2", "ABC-3"])
		self.assertEqual(by_key["ABC-2"]["reasons"], ["github_key"])
		self.assertEqual(by_key["ABC-2"]["prs"][0]["url"], "https://github.com/Org/app/pull/12")
		self.assertEqual(by_key["ABC-2"]["prs"][0]["branch"], "feature/ABC-2-pdf")
		self.assertTrue(by_key["ABC-1"]["prs"][0]["mine"])
		self.assertEqual(by_key["ABC-3"]["commits"][0]["title"], "ABC-3 tidy imports")
		looked_up = [path.rsplit("/", 1)[1] for path in client.fake.paths() if path.startswith("/rest/api/3/issue/")]
		self.assertNotIn("PR-3647", looked_up)
		self.assertNotIn("UTF-8", looked_up)

	def test_unknown_github_key_is_dropped_silently(self):
		github = {"prs_raised": [{"repo": "O/a", "number": 1, "title": "ZZZ-77 whatever", "url": "https://github.com/O/a/pull/1"}]}
		digest = self.digest(client_for(jira_handler([issue("ABC-1")], search=[])), github=github)
		self.assertEqual((digest["tickets"], digest["missing_keys"], digest["errors"]), ([], [], []))

	def test_dev_status_is_opt_in_and_merges_with_github_prs(self):
		def dev(path, query):
			if path.endswith("/summary"):
				return 200, {"summary": {"pullrequest": {"overall": {"count": 2}, "byInstanceType": {"GitHub": {"count": 2}}}}}
			return 200, {"detail": [{"pullRequests": [
				{"id": "#11", "name": "ABC-1 fix export", "url": "https://github.com/Org/app/pull/11", "status": "MERGED", "repositoryName": "Org/app", "source": {"branch": "abc-1"}},
				{"id": "#99", "name": "teammate PR", "url": "https://github.com/Org/app/pull/99", "status": "OPEN", "repositoryName": "Org/app"},
			]}]}

		off = client_for(full_handler(dev))
		self.digest(off, github=GITHUB)
		self.assertFalse([path for path in off.fake.paths() if "dev-status" in path])
		on = client_for(full_handler(dev))
		digest = self.digest(on, github=GITHUB, dev_status=True)
		prs = {pr["number"]: pr for pr in next(t for t in digest["tickets"] if t["key"] == "ABC-1")["prs"]}
		self.assertEqual(prs[11]["sources"], ["dev-status", "github"])
		self.assertTrue(prs[11]["mine"])
		self.assertEqual(prs[99]["sources"], ["dev-status"])
		self.assertFalse(prs[99]["mine"])

	def test_dev_status_failure_trips_the_breaker_once(self):
		client = client_for(full_handler(lambda path, query: (403, {})))
		digest = self.digest(client, github=GITHUB, dev_status=True)
		self.assertEqual(len([path for path in client.fake.paths() if "dev-status" in path]), 1)
		self.assertEqual(len([error for error in digest["errors"] if "dev-status" in error]), 1)

	def test_digest_is_deterministic_and_carries_no_identity(self):
		first = self.digest(client_for(full_handler()), keys=["ABC-9"], github=GITHUB)
		second = self.digest(client_for(full_handler()), keys=["ABC-9"], github=GITHUB)
		self.assertEqual(json.dumps(first), json.dumps(second))
		text = json.dumps(first)
		for secret in (EMAIL, "acct-1", "Example Employee", TOKEN):
			self.assertNotIn(secret, text)


DIGEST = {
	"version": 1, "date": "2026-09-08", "site": SITE,
	"tickets": [
		{"key": "ABC-1", "id": "1", "url": f"{SITE}/browse/ABC-1", "summary": "Fix export", "status": "In Review", "reasons": ["assigned_updated"],
		 "prs": [
			{"repo": "Org/app", "number": 11, "url": "https://github.com/Org/app/pull/11", "title": "ABC-1 fix", "sources": ["github"], "mine": True},
			{"repo": "Org/app", "number": 99, "url": "https://github.com/Org/app/pull/99", "title": "mate", "sources": ["dev-status"], "mine": False},
		 ]},
		{"key": "ABC-2", "id": "2", "url": f"{SITE}/browse/ABC-2", "summary": "Other", "status": "Done", "reasons": ["listed"], "prs": []},
		{"key": "ABC-3", "id": "3", "url": f"{SITE}/browse/ABC-3", "summary": "Pr only", "status": "To Do", "reasons": ["github_key"], "prs": []},
	],
	"missing_keys": [], "errors": [],
}


class ResolveTests(unittest.TestCase):
	def test_ticket_link_first_pr_links_deduped_jira_line_added(self):
		entries = [entry(links=[{"label": "mine", "url": "https://github.com/Org/app/pull/11/"}], tickets=["ABC-1"])]
		original = copy.deepcopy(entries)
		resolved, warnings = ts_jira.resolve_tickets(entries, DIGEST, site=SITE)
		self.assertEqual(entries, original)
		links = resolved[0]["links"]
		self.assertEqual(links[0], {"label": "ABC-1", "url": f"{SITE}/browse/ABC-1", "kind": "ticket", "title": "Fix export", "status": "In Review"})
		self.assertEqual([link["url"] for link in links[1:]], ["https://github.com/Org/app/pull/11/"])  # model link kept, mine-PR not repeated, teammate PR never added
		self.assertTrue(resolved[0]["description"].endswith("\n\nJira: ABC-1 — Fix export [In Review]"))
		self.assertEqual(warnings, ["Jira tickets matching no entry: ABC-2 — ask the user whether they are lines and how long they took"])

	def test_digest_prs_are_linked_when_the_model_did_not(self):
		resolved, _ = ts_jira.resolve_tickets([entry(tickets=["ABC-1"])], DIGEST, site=SITE)
		self.assertEqual([(link["kind"], link["label"]) for link in resolved[0]["links"]], [("ticket", "ABC-1"), ("pr", "PR-11")])

	def test_resolve_is_idempotent(self):
		entries = [entry(tickets=["ABC-1", f"{SITE}/browse/ABC-2"]), entry(label="Other")]
		once, _ = ts_jira.resolve_tickets(entries, DIGEST, site=SITE)
		twice, _ = ts_jira.resolve_tickets(once, DIGEST, site=SITE)
		self.assertEqual(json.dumps(once, sort_keys=True), json.dumps(twice, sort_keys=True))
		self.assertEqual(once[0]["description"].count("Jira: ABC-1"), 1)
		self.assertEqual(len(once), 2)  # never creates entries
		self.assertEqual([row["hours"] for row in once], [1.0, 1.0])

	def test_pulled_row_keeps_its_line_and_link_when_a_ticket_is_hand_added(self):
		description = "Did the thing.\n\nJira: ABC-1 — Old summary [Open]"
		pulled = entry(description=description, links=[{"url": f"{SITE}/browse/ABC-1"}], tickets=[])
		untouched, warnings = ts_jira.resolve_tickets([pulled], DIGEST, site=SITE)
		self.assertEqual(untouched[0]["description"], description)
		self.assertEqual(untouched[0]["links"], pulled["links"])
		self.assertEqual(warnings, ["Jira tickets matching no entry: ABC-2 — ask the user whether they are lines and how long they took"])
		pulled["tickets"] = ["ABC-1", "ABC-2"]
		edited, _ = ts_jira.resolve_tickets([pulled], DIGEST, site=SITE)
		self.assertEqual(edited[0]["description"].count("Jira: ABC-1"), 1)  # no second line for ABC-1
		self.assertIn("Jira: ABC-2 — Other [Done]", edited[0]["description"])
		self.assertEqual([link["url"] for link in edited[0]["links"]].count(f"{SITE}/browse/ABC-1"), 1)  # upgraded in place
		self.assertEqual(next(l for l in edited[0]["links"] if l["label"] == "ABC-1")["status"], "In Review")

	def test_without_digest_or_site_it_never_raises(self):
		resolved, warnings = ts_jira.resolve_tickets([entry(tickets=["ABC-5"])], None, site=None)
		self.assertTrue(resolved[0]["description"].endswith("Jira: ABC-5"))
		self.assertEqual(resolved[0]["links"], [])
		self.assertTrue(any("ABC-5" in warning for warning in warnings))
		derived, _ = ts_jira.resolve_tickets([entry(tickets=["ABC-5"], links=[{"url": f"{SITE}/browse/ABC-5"}])], None, site=None)
		self.assertEqual(derived[0]["links"][0]["kind"], "ticket")
		with_site, _ = ts_jira.resolve_tickets([entry(tickets=["ABC-5"])], None, site=SITE)
		self.assertEqual(with_site[0]["links"][0]["url"], f"{SITE}/browse/ABC-5")

	def test_ticket_missing_from_digest_is_linked_with_a_warning_and_other_host_is_not_linked(self):
		resolved, warnings = ts_jira.resolve_tickets([entry(tickets=["ABC-8"])], DIGEST, site=SITE)
		self.assertEqual(resolved[0]["links"][0]["url"], f"{SITE}/browse/ABC-8")
		self.assertNotIn("title", resolved[0]["links"][0])
		self.assertTrue(any("ABC-8" in warning for warning in warnings))
		foreign, warnings = ts_jira.resolve_tickets([entry(tickets=["https://evil.atlassian.net/browse/ABC-1"])], DIGEST, site=SITE)
		self.assertEqual(foreign[0]["links"], [])
		self.assertTrue(warnings)

	def test_junk_tickets_are_a_spec_error(self):
		with self.assertRaises(ts_common.SuiteError):
			ts_jira.resolve_tickets([entry(tickets="ABC-1")], DIGEST, site=SITE)
		with self.assertRaises(ts_common.SuiteError):
			ts_jira.resolve_tickets([entry(tickets=["nope"])], DIGEST, site=SITE)

	def test_load_digest_rejects_a_tampered_site(self):
		with tempfile.TemporaryDirectory() as tmp:
			self.assertIsNone(ts_jira.load_jira_digest(tmp, "2026-09-08"))
			path = Path(tmp) / "jira_2026-09-08.json"
			path.write_text(json.dumps({**DIGEST, "site": "https://evil.example"}))
			with self.assertRaises(ts_common.SuiteError):
				ts_jira.load_jira_digest(tmp, "2026-09-08")
			path.write_text(json.dumps(DIGEST))
			self.assertEqual(ts_jira.load_jira_digest(tmp, "2026-09-08")["site"], SITE)


class CliTests(unittest.TestCase):
	def setUp(self):
		tmp = tempfile.TemporaryDirectory()
		self.addCleanup(tmp.cleanup)
		self.tmp = Path(tmp.name)
		patch = mock.patch.dict(os.environ, {}, clear=True)
		patch.start()
		self.addCleanup(patch.stop)
		self.output = []
		self.profile = {"out_dir": str(self.tmp), "utc_offset": "+05:30"}

	def run_cli(self, argv, *, fake=None):
		parser = argparse.ArgumentParser()
		commands = parser.add_subparsers(dest="command", required=True)
		handlers = ts_jira.add_parsers(commands)
		args = parser.parse_args(["jira", *argv])
		env = ts_common.Env(lambda: self.profile, lambda: self.profile, lambda site: None, self.output.append)
		real = ts_jira.JiraClient
		factory = (lambda creds: real(creds, transport=fake, sleep=lambda s: None)) if fake else real
		with mock.patch.object(ts_jira, "JiraClient", factory):
			return handlers["jira"](args, env)

	def test_check_lists_everything_missing_exit_2_without_network(self):
		fake = Fake(jira_handler())
		self.assertEqual(self.run_cli(["--check"], fake=fake), 2)
		text = "\n".join(self.output)
		self.assertIn("missing:", text)
		for needle in ("site", "email", "JIRA_API_TOKEN"):
			self.assertIn(needle, text)
		self.assertEqual(fake.calls, [])

	def test_pasted_url_is_never_a_destination(self):
		fake = Fake(jira_handler())
		os.environ.update({"JIRA_API_TOKEN": TOKEN, "JIRA_EMAIL": EMAIL})
		code = self.run_cli(["--date", "2026-09-08", "--keys", "https://evil.atlassian.net/browse/ABC-1"], fake=fake)
		self.assertEqual(code, 2)
		self.assertIn("missing: Jira site", "\n".join(self.output))
		self.assertIn("https://evil.atlassian.net", "\n".join(self.output))
		self.assertEqual(fake.calls, [])
		os.environ["JIRA_SITE"] = "acme.atlassian.net"
		with self.assertRaises(ts_common.SuiteError):
			self.run_cli(["--date", "2026-09-08", "--keys", "https://evil.atlassian.net/browse/ABC-1"], fake=fake)
		self.assertEqual(fake.calls, [])

	def test_check_ok_reports_the_display_name_only(self):
		os.environ.update({"JIRA_API_TOKEN": TOKEN})
		self.profile.update(jira_site="acme.atlassian.net", jira_email=EMAIL)
		self.assertEqual(self.run_cli(["--check"], fake=Fake(jira_handler())), 0)
		text = "\n".join(self.output)
		self.assertIn("ok: Example Employee", text)
		self.assertNotIn(TOKEN, text)
		self.assertNotIn(EMAIL, text)

	def test_date_is_required_unless_checking(self):
		os.environ.update({"JIRA_API_TOKEN": TOKEN, "JIRA_SITE": "acme.atlassian.net", "JIRA_EMAIL": EMAIL})
		with self.assertRaises(ts_common.SuiteError):
			self.run_cli([], fake=Fake(jira_handler()))

	def test_run_writes_a_private_digest_and_merges_the_default_github_file(self):
		os.environ.update({"JIRA_API_TOKEN": TOKEN, "JIRA_SITE": "acme.atlassian.net", "JIRA_EMAIL": EMAIL})
		(self.tmp / "github_2026-09-08.json").write_text(json.dumps(GITHUB))
		fake = Fake(full_handler())
		self.assertEqual(self.run_cli(["--date", "2026-09-08"], fake=fake), 0)
		path = self.tmp / "jira_2026-09-08.json"
		digest = json.loads(path.read_text())
		self.assertEqual([item["key"] for item in digest["tickets"]], ["ABC-1", "ABC-2", "ABC-3"])
		self.assertEqual(path.stat().st_mode & 0o777, 0o600)
		text = "\n".join(self.output)
		self.assertIn("ABC-1", text)
		for secret in (TOKEN, EMAIL):
			self.assertNotIn(secret, text)
			self.assertNotIn(secret, path.read_text())

	def test_abbreviated_flags_are_refused(self):
		with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
			self.run_cli(["--dev", "--check"])


if __name__ == "__main__":
	unittest.main()
