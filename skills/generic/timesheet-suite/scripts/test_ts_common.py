"""Unit tests for ts_common.py — run from the skill folder:

    python3 -m unittest discover -s scripts -p 'test_ts_common.py'
"""
from __future__ import annotations

import contextlib
import http.server
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ts_common  # noqa: E402
from ts_common import SuiteError  # noqa: E402


def mode(path) -> int:
	return stat.S_IMODE(os.stat(path).st_mode)


class SiteFrappeTests(unittest.TestCase):
	def test_accepted_forms(self):
		cases = {
			"erp.example.com": "https://erp.example.com",
			"Erp.Example.com/": "https://erp.example.com",
			"  https://erp.example.com  ": "https://erp.example.com",
			"https://erp.acme.in/app/timesheet/view?x=1#y": "https://erp.acme.in",
			"HTTPS://x.com:443": "https://x.com",
			"x.com:8443": "https://x.com:8443",
			"x.com.": "https://x.com",
			"bench": "http://bench.localhost:8000",
			"Bench": "http://bench.localhost:8000",
			"localhost:8000": "http://localhost:8000",
			"127.0.0.1:8000": "http://127.0.0.1:8000",
			"mysite.localhost:8000": "http://mysite.localhost:8000",
			"http://[::1]:8000": "http://[::1]:8000",
			"https://localhost:8000": "https://localhost:8000",
			"http://localhost": "http://localhost",
			"münchen.example.de": "https://xn--mnchen-3ya.example.de",
		}
		for value, expected in cases.items():
			with self.subTest(value=value):
				result = ts_common.normalise_site(value)
				self.assertEqual(result, expected)
				self.assertEqual(ts_common.normalise_site(result), result)

	def test_plain_http_to_a_remote_host_is_refused(self):
		for value in ("http://remote.example.com", "http://10.0.0.5:8000"):
			with self.subTest(value=value), self.assertRaisesRegex(SuiteError, "plain http"):
				ts_common.normalise_site(value)

	def test_userinfo_is_refused_and_never_echoed(self):
		with self.assertRaises(SuiteError) as caught:
			ts_common.normalise_site("https://alice:hunter2@x.com")
		self.assertNotIn("hunter2", str(caught.exception))
		self.assertNotIn("alice", str(caught.exception))

	def test_garbage_is_refused_without_echoing_it(self):
		garbage = [
			None,
			"",
			"   ",
			"not a site",
			"token abc:def",
			"ftp://x.com",
			"javascript:alert(1)",
			"https://",
			"x.com:99999",
			"x.com:0",
			"x.com:80a",
			"http://x.com:80a",
			"-bad.com",
			"bad-.com",
			"a..b",
			".leading.com",
			"a" * 64 + ".com",
			"a" * 60 + "." + "b" * 60 + "." + "c" * 60 + "." + "d" * 60 + "." + "e" * 60 + ".com",
			"é" * 64 + ".com",
			"https://x.com/\x00",
			"x_y.com",
		]
		for value in garbage:
			with self.subTest(value=value):
				with self.assertRaises(SuiteError) as caught:
					ts_common.normalise_site(value)
				self.assertNotIn("abc:def", str(caught.exception))

	def test_slug_host_and_bundled_host_are_path_safe(self):
		self.assertEqual(ts_common.site_host("https://erp.example.com"), "erp.example.com")
		self.assertEqual(ts_common.site_host("http://mysite.localhost:8000"), "mysite.localhost:8000")
		self.assertEqual(ts_common.site_slug("https://erp.acme.in"), "erp.acme.in")
		self.assertEqual(ts_common.site_slug("http://mysite.localhost:8000"), "mysite.localhost_8000")
		for site in ("https://a/../../x", "http://[::1]:8000", "https://.hidden.com"):
			with self.subTest(site=site):
				slug = ts_common.site_slug(site)
				self.assertRegex(slug, r"^[a-z0-9_][a-z0-9._-]*$")
				self.assertNotIn("/", slug)


class SiteJiraTests(unittest.TestCase):
	def test_only_cloud_origins_are_accepted(self):
		cases = {
			"acme.atlassian.net": "https://acme.atlassian.net",
			"https://Acme.atlassian.net/browse/ABC-1?x=1": "https://acme.atlassian.net",
			"https://acme.atlassian.net:443/": "https://acme.atlassian.net",
			"acme.atlassian.net.": "https://acme.atlassian.net",
		}
		for value, expected in cases.items():
			with self.subTest(value=value):
				self.assertEqual(ts_common.normalise_site(value, kind="jira"), expected)

	def test_everything_else_is_refused(self):
		for value in (
			"acme",
			"localhost",
			"evil.com",
			"acme.atlassian.net.evil.com",
			"evilatlassian.net",
			"a.b.atlassian.net",
			"http://acme.atlassian.net",
			"https://user:pw@acme.atlassian.net",
			"acme.atlassian.net:8443",
			"https://evil.com/acme.atlassian.net",
			"",
		):
			with self.subTest(value=value), self.assertRaises(SuiteError):
				ts_common.normalise_site(value, kind="jira")

	def test_unknown_kind_is_a_programming_error(self):
		with self.assertRaises(ValueError):
			ts_common.normalise_site("x.com", kind="other")


class SecretTests(unittest.TestCase):
	def test_environment_secrets_match_as_substrings(self):
		env = {"FRAPPE_API_SECRET": "s3cr3t-value", "GITHUB_TOKEN": "abc"}
		with mock.patch.dict(os.environ, env, clear=True):
			self.assertTrue(ts_common.looks_like_secret("token key:s3cr3t-value"))
			self.assertFalse(ts_common.looks_like_secret("abc"))  # shorter than 6 characters: ignored

	def test_known_prefixes(self):
		with mock.patch.dict(os.environ, {}, clear=True):
			for value in ("ghp_abc123", "gho_x", "ghs_x", "github_pat_11AAA", "ATATT3xFfGF0", "xoxb-1-2", "xoxp-1", "me ghp_abc"):
				with self.subTest(value=value):
					self.assertTrue(ts_common.looks_like_secret(value))

	def test_ordinary_values_are_not_secrets(self):
		with mock.patch.dict(os.environ, {"FRAPPE_API_KEY": "a-real-key"}, clear=True):
			for value in (
				"Acme-Rollout",
				"PROJ-0019",
				"HR-EMP-00001",
				"Example Company Pvt Ltd",
				"https://erp.example.com",
				"",
			):
				with self.subTest(value=value):
					self.assertFalse(ts_common.looks_like_secret(value))


class CleanCredentialTests(unittest.TestCase):
	def test_strips_and_maps_empty_to_none(self):
		self.assertEqual(ts_common.clean_credential("  tok-123\n", "GITHUB_TOKEN"), "tok-123")
		for empty in (None, "", "   \n\t "):
			self.assertIsNone(ts_common.clean_credential(empty, "GITHUB_TOKEN"))

	def test_control_characters_are_refused_naming_only_the_label(self):
		for value in ("abc\x00def", "abc\ndef", "ab\tc-secret", "x\x7fy-secret", "\x1b[31msecret"):
			with self.subTest(value=value):
				with self.assertRaises(SuiteError) as caught:
					ts_common.clean_credential(value, "FRAPPE_API_SECRET")
				message = str(caught.exception)
				self.assertEqual(message, "FRAPPE_API_SECRET contains control characters")
				self.assertNotIn("secret", message.replace("FRAPPE_API_SECRET", ""))


class PrivateWriteTests(unittest.TestCase):
	def setUp(self):
		tmp = tempfile.TemporaryDirectory()
		self.addCleanup(tmp.cleanup)
		self.root = Path(tmp.name)

	def test_new_file_and_dirs_are_private(self):
		path = self.root / "a" / "b" / "profile.json"
		ts_common.write_private_json(path, {"k": "é"})
		self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"k": "é"})
		self.assertEqual(mode(path), 0o600)
		self.assertEqual(mode(path.parent), 0o700)

	def test_config_dir_is_forced_to_0700_even_when_it_pre_exists_loose(self):
		home = self.root / "cfg"
		home.mkdir()
		home.chmod(0o755)
		path = home / "profile.json"
		path.write_text("{}")
		path.chmod(0o644)
		with mock.patch.dict(os.environ, {"TIMESHEET_SUITE_HOME": str(home)}):
			ts_common.write_private_text(path, "hello\n")
			ts_common.write_private_text(home / "catalogues" / "site" / "projects.csv", "x")
		self.assertEqual(path.read_text(), "hello\n")
		self.assertEqual(mode(home), 0o700)
		self.assertEqual(mode(path), 0o600)

	def test_a_caller_supplied_existing_dir_keeps_its_mode(self):
		out = self.root / "Downloads"
		out.mkdir()
		out.chmod(0o755)
		ts_common.write_private_text(out / "timesheet.json", "{}")
		self.assertEqual(mode(out), 0o755)
		self.assertEqual(mode(out / "timesheet.json"), 0o600)

	def test_every_directory_it_creates_is_0700_but_existing_ancestors_are_untouched(self):
		base = self.root / "existing"
		base.mkdir()
		base.chmod(0o755)
		old = os.umask(0o000)
		try:
			ts_common.write_private_text(base / "a" / "b" / "c" / "f.txt", "x")
		finally:
			os.umask(old)
		self.assertEqual(mode(base), 0o755)
		for name in ("a", "a/b", "a/b/c"):
			self.assertEqual(mode(base / name), 0o700, name)

	def test_filesystem_failures_become_suite_errors_without_a_traceback_type(self):
		blocker = self.root / "file"
		blocker.write_text("x")
		with self.assertRaises(SuiteError):
			ts_common.write_private_text(blocker / "child" / "f.txt", "x")
		locked = self.root / "locked"
		locked.mkdir()
		locked.chmod(0o500)
		self.addCleanup(locked.chmod, 0o700)
		if os.geteuid() != 0:
			with self.assertRaises(SuiteError):
				ts_common.write_private_text(locked / "f.txt", "x")

	def test_a_failed_replace_keeps_the_old_file_and_leaves_no_temp_files(self):
		path = self.root / "profile.json"
		ts_common.write_private_text(path, "old")
		with mock.patch("os.replace", side_effect=OSError("disk gone")):
			with self.assertRaises(SuiteError):
				ts_common.write_private_text(path, "new")
		self.assertEqual(path.read_text(), "old")
		self.assertEqual(os.listdir(self.root), ["profile.json"])


class EmailTests(unittest.TestCase):
	def test_valid_address_is_returned_stripped(self):
		self.assertEqual(ts_common.validate_email("  me@example.com "), "me@example.com")

	def test_pasted_credentials_and_junk_are_refused_without_echo(self):
		for value in ("me@example.com:tok3n-xyz", "me @example.com", "me@example.com tok", "me", "@x.com", "me@x", "", None):
			with self.subTest(value=value):
				with self.assertRaises(SuiteError) as caught:
					ts_common.validate_email(value)
				self.assertNotIn("tok3n-xyz", str(caught.exception))


class DescriptionTests(unittest.TestCase):
	def test_legacy_layout_is_text_blank_line_then_ref_lines(self):
		links = [{"label": "PR-1", "url": "https://example.com/pr/1"}, {"url": "http://example.com/2"}]
		self.assertEqual(
			ts_common.render_description("Did the thing properly.", links),
			"Did the thing properly.\n\nRef: https://example.com/pr/1\nRef: http://example.com/2",
		)
		self.assertEqual(ts_common.render_description("only text", []), "only text")
		self.assertEqual(ts_common.render_description("", [{"url": "https://e.com/x"}]), "Ref: https://e.com/x")
		self.assertEqual(ts_common.render_description("", []), "")

	def test_only_http_links_are_written_and_duplicates_collapse(self):
		links = [
			{"url": "javascript:alert(1)"},
			{"url": "ftp://x/y"},
			{"label": "no url"},
			{"url": "https://e.com/a"},
			{"url": "https://e.com/a"},
			{"url": "https://e.com/b\nRef: https://evil.com"},
		]
		self.assertEqual(ts_common.render_description("t", links), "t\n\nRef: https://e.com/a")

	def test_split_inverts_render_and_a_second_build_is_byte_identical(self):
		cases = [
			("Fixed it.", [{"url": "https://e.com/1"}, {"url": "https://e.com/2"}]),
			("Jira: ABC-1 — Login bug [In Progress]\nSecond line", [{"url": "https://e.com/1"}]),
			("Multi\n\nparagraph text", []),
			("", [{"url": "https://e.com/1"}]),
			("", []),
		]
		for text, links in cases:
			with self.subTest(text=text):
				rendered = ts_common.render_description(text, links)
				self.assertEqual(ts_common.split_description(rendered), (text, links))
				again = ts_common.render_description(*ts_common.split_description(rendered))
				self.assertEqual(again, rendered)

	def test_split_only_lifts_trailing_http_ref_lines(self):
		desc = "Ref: https://e.com/in-the-middle\nmore text\nRef: ftp://x/y"
		self.assertEqual(ts_common.split_description(desc), (desc, []))
		desc = "Body\n\nRef: https://e.com/1\nRef: ftp://x/y\nRef: https://e.com/2"
		text, links = ts_common.split_description(desc)
		self.assertEqual((text, links), ("Body\n\nRef: https://e.com/1\nRef: ftp://x/y", [{"url": "https://e.com/2"}]))
		self.assertEqual(ts_common.split_description(None), ("", []))


class SmallHelperTests(unittest.TestCase):
	def test_suite_error_carries_an_exit_code(self):
		class Setup(SuiteError):
			exit_code = 2

		self.assertEqual(SuiteError("x").exit_code, 1)
		self.assertEqual(Setup("x").exit_code, 2)

	def test_config_dir_follows_the_environment_variable(self):
		with mock.patch.dict(os.environ, {"TIMESHEET_SUITE_HOME": "/tmp/ts-home"}):
			self.assertEqual(ts_common.config_dir(), Path("/tmp/ts-home"))
		with mock.patch.dict(os.environ, {}, clear=True), mock.patch("pathlib.Path.home", return_value=Path("/h")):
			self.assertEqual(ts_common.config_dir(), Path("/h/.config/timesheet-suite"))

	def test_out_dir_precedence_is_override_then_profile_then_default(self):
		self.assertEqual(ts_common.out_dir_for({"out_dir": "/p"}, "/o"), Path("/o"))
		self.assertEqual(ts_common.out_dir_for({"out_dir": "/p"}), Path("/p"))
		self.assertEqual(ts_common.out_dir_for(None), Path(ts_common.DEFAULT_OUT_DIR).expanduser())
		self.assertEqual(ts_common.out_dir_for({"out_dir": ""}, ""), Path(ts_common.DEFAULT_OUT_DIR).expanduser())

	def test_read_json_reports_missing_and_invalid_files(self):
		with tempfile.TemporaryDirectory() as tmp:
			bad = Path(tmp) / "bad.json"
			bad.write_text("{nope")
			with self.assertRaisesRegex(SuiteError, "No such file"):
				ts_common.read_json(Path(tmp) / "missing.json")
			with self.assertRaisesRegex(SuiteError, "not valid JSON"):
				ts_common.read_json(bad)

	def test_read_json_turns_every_unreadable_shape_into_a_suite_error(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp)
			binary = root / "binary.json"
			binary.write_bytes(b"\xff\xfe\x00{")
			deep = root / "deep.json"
			deep.write_text("[" * 200000)
			scalar = root / "list.json"
			scalar.write_text("[1, 2]")
			with self.assertRaises(SuiteError):
				ts_common.read_json(root)  # a directory
			for path in (binary, deep):
				with self.subTest(path=path.name), self.assertRaises(SuiteError):
					ts_common.read_json(path)
			with self.assertRaisesRegex(SuiteError, "must be a JSON object"):
				ts_common.read_json(scalar)
			ok = root / "ok.json"
			ok.write_text('{"a": 1}')
			self.assertEqual(ts_common.read_json(ok), {"a": 1})

	def test_env_defaults_to_print(self):
		env = ts_common.Env(load_profile=dict, read_profile=lambda: None, client_factory=lambda site: site)
		self.assertIs(env.out, print)


class Loopback:
	"""A throwaway HTTP server that records every request and redirects on demand."""

	def __init__(self, test: unittest.TestCase, redirect_to: str | None = None):
		self.requests: list[tuple[str, str, dict]] = []
		outer = self

		class Handler(http.server.BaseHTTPRequestHandler):
			def log_message(self, *args):
				pass

			def respond(self):
				length = int(self.headers.get("Content-Length") or 0)
				if length:
					self.rfile.read(length)
				outer.requests.append((self.command, self.path, dict(self.headers.items())))
				if self.path == "/cross":
					self.send_response(302)
					self.send_header("Location", (redirect_to or "") + "/landing")
				elif self.path == "/same":
					self.send_response(302)
					self.send_header("Location", "/landing")
				else:
					self.send_response(200)
					self.send_header("Content-Type", "application/json")
					body = b'{"ok": true}'
					self.send_header("Content-Length", str(len(body)))
					self.end_headers()
					self.wfile.write(body)
					return
				self.send_header("Content-Length", "0")
				self.end_headers()

			do_GET = do_POST = do_PUT = respond

		self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
		self.origin = f"http://127.0.0.1:{self.server.server_address[1]}"
		thread = threading.Thread(target=self.server.serve_forever, daemon=True)
		thread.start()
		test.addCleanup(self.stop, thread)

	def stop(self, thread):
		self.server.shutdown()
		self.server.server_close()
		thread.join(5)

	def paths(self):
		return [path for _, path, _ in self.requests]


class OpenerTests(unittest.TestCase):
	def opener(self, origin, follow_same_origin_get):
		return ts_common.build_opener(origin, follow_same_origin_get, extra_handlers=[urllib.request.ProxyHandler({})])

	def get(self, opener, url, method="GET", data=None):
		request = urllib.request.Request(
			url, data=data, method=method, headers={"Authorization": "token key:secret"}
		)
		with opener.open(request, timeout=5) as response:
			return json.loads(response.read())

	def test_cross_origin_redirect_is_refused_and_the_target_never_sees_a_request(self):
		other = Loopback(self)
		first = Loopback(self, redirect_to=other.origin)
		with self.assertRaisesRegex(SuiteError, "different"):
			self.get(self.opener(first.origin, True), first.origin + "/cross")
		self.assertEqual(first.paths(), ["/cross"])
		self.assertEqual(other.requests, [])

	def test_cross_origin_is_refused_when_following_is_off_too(self):
		other = Loopback(self)
		first = Loopback(self, redirect_to=other.origin)
		with self.assertRaises(SuiteError):
			self.get(self.opener(first.origin, False), first.origin + "/cross")
		self.assertEqual(other.requests, [])

	def test_same_origin_get_redirect_is_followed_only_when_allowed(self):
		server = Loopback(self)
		self.assertEqual(self.get(self.opener(server.origin, True), server.origin + "/same"), {"ok": True})
		self.assertEqual(server.paths(), ["/same", "/landing"])
		refusing = Loopback(self)
		with self.assertRaises(SuiteError):
			self.get(self.opener(refusing.origin, False), refusing.origin + "/same")
		self.assertEqual(refusing.paths(), ["/same"])

	def test_redirected_writes_are_never_replayed(self):
		server = Loopback(self)
		for method in ("POST", "PUT"):
			with self.subTest(method=method), self.assertRaises(SuiteError):
				self.get(self.opener(server.origin, True), server.origin + "/same", method=method, data=b"{}")
		self.assertNotIn("/landing", server.paths())

	def test_origin_normalises_default_ports_and_case(self):
		self.assertEqual(ts_common.origin_of("https://X.com"), ("https", "x.com", 443))
		self.assertEqual(ts_common.origin_of("https://x.com:443/a"), ("https", "x.com", 443))
		self.assertEqual(ts_common.origin_of("http://x.com"), ("http", "x.com", 80))
		self.assertEqual(ts_common.origin_of("http://x.com:8000"), ("http", "x.com", 8000))

	def test_origin_can_be_given_as_a_tuple(self):
		server = Loopback(self)
		host, port = server.origin.removeprefix("http://").split(":")
		opener = self.opener(("http", host, int(port)), True)
		self.assertEqual(self.get(opener, server.origin + "/same"), {"ok": True})


if __name__ == "__main__":
	unittest.main()
