"""Unit tests for ts_post.py. Run from the skill folder:

    python3 -m unittest discover -s scripts -p 'test_ts_post*.py' -v
"""
from __future__ import annotations

import argparse
import contextlib
import email.message
import io
import json
import os
import sys
import traceback
import unittest
import urllib.error
import urllib.request
import urllib.response
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ts_post  # noqa: E402
from ts_common import Env, SuiteError, build_opener, origin_of  # noqa: E402
from ts_testkit import TempHome  # noqa: E402

DATE = "2026-09-08"
TOKEN_PART = "zQ9xKp2LmN4vB7cR1tY6wE"
DISCORD_URL = f"https://discord.com/api/webhooks/123456789012345678/{TOKEN_PART}"
SLACK_URL = f"https://hooks.slack.com/services/T0000000/B0000000/{TOKEN_PART}"
URLS = {"discord": DISCORD_URL, "slack": SLACK_URL}
ENV_VARS = {"discord": "DISCORD_WEBHOOK_URL", "slack": "SLACK_WEBHOOK_URL"}
MESSAGE = "Today's (Sep 8) Update:\n1. Fixed login\n2. Reviewed PRs\n3. Wrote docs\n4. Planned tomorrow"
FILES = {"discord": f"discord_{DATE}.md", "slack": f"chat_slack_{DATE}.txt"}


class FakeResponse:
	def __init__(self, status=204, body=b""):
		self.status = status
		self._body = body

	def __enter__(self):
		return self

	def __exit__(self, *_exc):
		return False

	def read(self, *_args):
		return self._body


class FakeOpener:
	"""Records every request; `result` is a response, or an exception to raise."""

	def __init__(self, result=None):
		self.result = FakeResponse() if result is None else result
		self.requests: list = []
		self.timeouts: list = []

	def open(self, request, timeout=None):
		self.requests.append(request)
		self.timeouts.append(timeout)
		if isinstance(self.result, BaseException):
			raise self.result
		return self.result


def http_error(code: int, body: bytes = b"", url: str = DISCORD_URL) -> urllib.error.HTTPError:
	return urllib.error.HTTPError(url, code, "Err", email.message.Message(), io.BytesIO(body))


class PostCase(TempHome):
	def setUp(self):
		super().setUp()
		self.out = self.home / "out"
		self.out.mkdir()
		patcher = mock.patch.dict(os.environ, {}, clear=False)
		patcher.start()
		self.addCleanup(patcher.stop)
		for name in ENV_VARS.values():
			os.environ.pop(name, None)

	def write_message(self, target="discord", text=MESSAGE):
		(self.out / FILES[target]).write_text(text + "\n", encoding="utf-8")

	def set_webhook(self, target="discord", url=None):
		os.environ[ENV_VARS[target]] = url or URLS[target]

	def run_post(self, *argv, opener=None, profile=None):
		"""Drive `post ...` through the real argparse wiring the way the composition root does."""
		root = argparse.ArgumentParser(allow_abbrev=False)
		handlers = ts_post.add_parsers(root.add_subparsers(dest="command", required=True))
		lines: list[str] = []
		env = Env(
			load_profile=lambda: profile or {},
			read_profile=lambda: profile or {},
			client_factory=lambda site: None,
			out=lines.append,
		)
		args = root.parse_args(["post", *argv])
		stderr = io.StringIO()
		opener = opener if opener is not None else FakeOpener()
		with mock.patch.object(ts_post, "build_opener", return_value=opener), contextlib.redirect_stderr(stderr):
			try:
				code = handlers[args.command](args, env)
			except SuiteError as exc:
				print(f"error: {exc}", file=sys.stderr)
				code = exc.exit_code
		self.last_output = "\n".join(lines) + "\n" + stderr.getvalue()
		return code, lines, opener

	def post(self, target="discord", *extra, **kwargs):
		return self.run_post("--date", DATE, "--target", target, "--out-dir", str(self.out), *extra, **kwargs)

	def confirmed(self, target="discord", *extra, **kwargs):
		return self.post(target, "--confirm-post", f"{target}/{DATE}", *extra, **kwargs)

	def audit_lines(self):
		path = self.home / "audit.log"
		return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

	def assert_no_url(self, *texts):
		for text in texts:
			for secret in (DISCORD_URL, SLACK_URL, TOKEN_PART, "123456789012345678", "T0000000/B0000000"):
				self.assertNotIn(secret, text)


class PreconditionTests(PostCase):
	def test_missing_message_file_says_to_run_build(self):
		self.set_webhook()
		code, _, opener = self.post()
		self.assertEqual(code, 1)
		self.assertIn("run `build`", self.last_output)
		self.assertIn(FILES["discord"], self.last_output)
		self.assertEqual(opener.requests, [])

	def test_unsupported_targets_list_the_supported_ones(self):
		for target in ("teams", "gmail", "whatsapp", "irc"):
			with self.subTest(target):
				code, _, opener = self.post(target)
				self.assertEqual(code, 1)
				self.assertIn("discord", self.last_output)
				self.assertIn("slack", self.last_output)
				self.assertEqual(opener.requests, [])

	def test_webhook_missing_from_env_names_the_variable(self):
		for target in ("discord", "slack"):
			with self.subTest(target):
				self.write_message(target)
				code, _, opener = self.confirmed(target)
				self.assertEqual(code, 1)
				self.assertIn(ENV_VARS[target], self.last_output)
				self.assertEqual(opener.requests, [])

	def test_blank_webhook_counts_as_missing(self):
		self.write_message()
		os.environ["DISCORD_WEBHOOK_URL"] = "   "
		code, _, _ = self.post()
		self.assertEqual(code, 1)
		self.assertIn("DISCORD_WEBHOOK_URL", self.last_output)

	def test_webhook_cannot_be_given_as_a_flag(self):
		self.write_message()
		with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
			self.post("discord", "--webhook", DISCORD_URL)

	def test_bad_date_is_rejected(self):
		self.set_webhook()
		code, _, _ = self.run_post("--date", "2026-13-40", "--target", "discord", "--out-dir", str(self.out))
		self.assertEqual(code, 1)

	def test_oversize_message_is_refused_before_sending(self):
		self.set_webhook()
		self.write_message(text="x" * 2001)
		code, _, opener = self.confirmed()
		self.assertEqual(code, 1)
		self.assertIn("limit", self.last_output)
		self.assertEqual(opener.requests, [])

	def test_profile_out_dir_is_used_without_the_flag(self):
		self.set_webhook()
		self.write_message()
		code, lines, _ = self.run_post("--date", DATE, "--target", "discord", profile={"out_dir": str(self.out)})
		self.assertEqual(code, 0)
		self.assertTrue(any(line.startswith("Dry run") for line in lines))


class WebhookValidationTests(PostCase):
	BAD = {
		"discord": [
			"http://discord.com/api/webhooks/1/abcdef",
			"https://evil.example.com/api/webhooks/1/abcdef",
			"https://discord.com.evil.example/api/webhooks/1/abcdef",
			"https://evil.example/https://discord.com/api/webhooks/1/abcdef",
			"https://discord.com/api/v10/channels/1/messages",
			"https://discord.com/api/webhooks/",
			"https://user:pw@discord.com/api/webhooks/1/abcdef",
			"https://discord.com:8443/api/webhooks/1/abcdef",
			"https://hooks.slack.com/services/T0/B0/abcdef",
			"ftp://discord.com/api/webhooks/1/abcdef",
			"discord.com/api/webhooks/1/abcdef",
			"https://discord.com/api/webhooks/1/abc def",
		],
		"slack": [
			"http://hooks.slack.com/services/T0/B0/abcdef",
			"https://hooks.slack.com.evil.example/services/T0/B0/abcdef",
			"https://slack.com/services/T0/B0/abcdef",
			"https://hooks.slack.com/api/chat.postMessage",
			"https://hooks.slack.com/services/",
			"https://discord.com/api/webhooks/1/abcdef",
		],
	}

	def test_wrong_scheme_host_or_path_is_refused_without_echoing_the_url(self):
		for target, urls in self.BAD.items():
			self.write_message(target)
			for url in urls:
				with self.subTest(target=target, url=url):
					self.set_webhook(target, url)
					for argv in ((), ("--confirm-post", f"{target}/{DATE}")):
						code, lines, opener = self.post(target, *argv)
						self.assertEqual(code, 1)
						self.assertIn(f"The {target} webhook URL is not a {target} webhook - refusing to send", self.last_output)
						self.assertNotIn(url, self.last_output)
						if url.split("/")[-1]:
							self.assertNotIn(url.split("/")[-1], self.last_output)
						self.assertEqual(opener.requests, [])
						self.assertEqual(lines, [])

	def test_every_documented_discord_host_and_slack_are_accepted(self):
		for host in ("discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com", "DISCORD.com"):
			url = f"https://{host}/api/webhooks/1/{TOKEN_PART}"
			self.assertEqual(ts_post.validate_webhook("discord", url), host.lower())
		self.assertEqual(ts_post.validate_webhook("slack", SLACK_URL), "hooks.slack.com")

	def test_post_message_validates_before_touching_the_network(self):
		opener = FakeOpener()
		for target, url in (("discord", "https://evil.example/api/webhooks/1/abcdef"), ("slack", DISCORD_URL)):
			with self.assertRaises(SuiteError) as caught:
				ts_post.post_message(url, target, "hi", opener=opener)
			self.assertNotIn(url, str(caught.exception))
		self.assertEqual(opener.requests, [])


class DryRunTests(PostCase):
	def test_dry_run_sends_nothing_and_shows_host_size_and_three_lines(self):
		self.set_webhook()
		self.write_message()
		code, lines, opener = self.post()
		self.assertEqual(code, 0)
		self.assertEqual(opener.requests, [])
		shown = "\n".join(lines)
		self.assertIn("target: discord", shown)
		self.assertIn("destination: discord.com", shown)
		self.assertIn(f"size: {len(MESSAGE)}/2000 chars", shown)
		for kept in MESSAGE.splitlines()[:3]:
			self.assertIn(kept, shown)
		self.assertNotIn("Planned tomorrow", shown)
		self.assertEqual(
			lines[-1],
			f"Dry run - nothing sent. Ask the user in this conversation, then re-run with --confirm-post discord/{DATE}",
		)
		self.assert_no_url(shown)
		self.assertEqual(self.audit_lines(), [])

	def test_slack_dry_run_reports_its_own_limit(self):
		self.set_webhook("slack")
		self.write_message("slack", "line one\nline two")
		code, lines, opener = self.post("slack")
		self.assertEqual(code, 0)
		self.assertEqual(opener.requests, [])
		self.assertIn("destination: hooks.slack.com", "\n".join(lines))
		self.assertIn("/4000 utf16", "\n".join(lines))
		self.assertIn(f"--confirm-post slack/{DATE}", lines[-1])

	def test_target_is_case_insensitive(self):
		self.set_webhook()
		self.write_message()
		code, lines, _ = self.run_post("--date", DATE, "--target", "Discord", "--out-dir", str(self.out))
		self.assertEqual(code, 0)
		self.assertIn("target: discord", lines)


class ConfirmationTests(PostCase):
	def test_wrong_confirm_token_sends_nothing_and_exits_2(self):
		self.set_webhook()
		self.write_message()
		for wrong in (f"slack/{DATE}", "discord/2026-09-09", "discord", DATE, "", f"discord/{DATE} "):
			with self.subTest(wrong=wrong):
				code, _, opener = self.post("discord", "--confirm-post", wrong)
				self.assertEqual(code, 2)
				self.assertIn(f"--confirm-post discord/{DATE}", self.last_output)
				self.assertEqual(opener.requests, [])
				self.assert_no_url(self.last_output)
		self.assertEqual(self.audit_lines(), [])

	def test_repost_alone_is_not_a_confirmation(self):
		self.set_webhook()
		self.write_message()
		code, lines, opener = self.post("discord", "--repost")
		self.assertEqual(code, 0)
		self.assertEqual(opener.requests, [])
		self.assertTrue(lines[-1].startswith("Dry run"))


class SendTests(PostCase):
	def test_discord_sends_exactly_one_request_with_the_right_json(self):
		self.set_webhook()
		self.write_message()
		code, lines, opener = self.confirmed()
		self.assertEqual(code, 0)
		self.assertEqual(len(opener.requests), 1)
		request = opener.requests[0]
		self.assertEqual(request.full_url, DISCORD_URL)
		self.assertEqual(request.get_method(), "POST")
		self.assertEqual(json.loads(request.data), {"content": MESSAGE, "allowed_mentions": {"parse": []}})
		self.assertEqual(request.get_header("Content-type"), "application/json")
		self.assertEqual(opener.timeouts, [30])
		self.assertEqual(lines[-1], f"Posted discord/{DATE} to discord.com (HTTP 204)")
		self.assert_no_url(self.last_output)

	def test_slack_sends_text_payload(self):
		self.set_webhook("slack")
		self.write_message("slack")
		opener = FakeOpener(FakeResponse(200, b"ok"))
		code, lines, opener = self.confirmed("slack", opener=opener)
		self.assertEqual(code, 0)
		self.assertEqual(len(opener.requests), 1)
		self.assertEqual(json.loads(opener.requests[0].data), {"text": MESSAGE})
		self.assertEqual(opener.requests[0].full_url, SLACK_URL)
		self.assertEqual(lines[-1], f"Posted slack/{DATE} to hooks.slack.com (HTTP 200)")

	def test_no_credentials_are_sent(self):
		self.set_webhook()
		self.write_message()
		with mock.patch.dict(os.environ, {"FRAPPE_API_KEY": "key-123456", "GITHUB_TOKEN": "ghp_abcdefghijkl"}):
			_, _, opener = self.confirmed()
		headers = {name.lower() for name, _ in opener.requests[0].header_items()}
		self.assertFalse(headers & {"authorization", "cookie", "x-api-key"})
		self.assertNotIn(b"key-123456", opener.requests[0].data)

	def test_unicode_message_is_sent_as_utf8(self):
		self.set_webhook()
		self.write_message(text="Update — café ✓")
		_, _, opener = self.confirmed()
		self.assertEqual(json.loads(opener.requests[0].data.decode("utf-8"))["content"], "Update — café ✓")

	def test_success_is_recorded_in_the_audit_log_without_the_url(self):
		self.set_webhook()
		self.write_message()
		self.confirmed()
		records = self.audit_lines()
		self.assertEqual(len(records), 1)
		self.assertEqual(
			{key: records[0][key] for key in ("command", "site", "doc", "status")},
			{"command": "post", "site": "discord.com", "doc": f"discord/{DATE}", "status": "posted"},
		)
		self.assert_no_url((self.home / "audit.log").read_text(encoding="utf-8"))

	def test_any_2xx_is_success_and_other_statuses_are_not(self):
		self.set_webhook()
		self.write_message()
		self.assertEqual(self.confirmed(opener=FakeOpener(FakeResponse(200)))[0], 0)
		with self.assertRaises(SuiteError) as caught:
			ts_post.post_message(DISCORD_URL, "discord", "hi", opener=FakeOpener(FakeResponse(304)))
		self.assertEqual(str(caught.exception), "HTTP 304")


class DuplicateGuardTests(PostCase):
	def test_second_post_is_refused_with_exit_2_unless_repost(self):
		self.set_webhook()
		self.write_message()
		self.assertEqual(self.confirmed()[0], 0)
		code, _, opener = self.confirmed()
		self.assertEqual(code, 2)
		self.assertEqual(opener.requests, [])
		self.assertIn("--repost", self.last_output)
		self.assertEqual(len(self.audit_lines()), 1)

		code, _, opener = self.confirmed("discord", "--repost")
		self.assertEqual(code, 0)
		self.assertEqual(len(opener.requests), 1)
		self.assertEqual(len(self.audit_lines()), 2)

	def test_dry_run_mentions_a_previous_post(self):
		self.set_webhook()
		self.write_message()
		self.confirmed()
		code, lines, opener = self.post()
		self.assertEqual(code, 0)
		self.assertEqual(opener.requests, [])
		self.assertIn("already posted", "\n".join(lines))

	def test_guard_is_per_target_and_per_date(self):
		self.set_webhook()
		self.set_webhook("slack")
		self.write_message()
		self.write_message("slack")
		self.assertEqual(self.confirmed()[0], 0)
		self.assertEqual(self.confirmed("slack")[0], 0)
		(self.out / f"discord_2026-09-09.md").write_text("next day\n", encoding="utf-8")
		code, _, opener = self.run_post(
			"--date", "2026-09-09", "--target", "discord", "--out-dir", str(self.out), "--confirm-post", "discord/2026-09-09"
		)
		self.assertEqual((code, len(opener.requests)), (0, 1))

	def test_failed_posts_and_foreign_log_lines_do_not_trigger_the_guard(self):
		self.set_webhook()
		self.write_message()
		(self.home / "audit.log").write_text(
			"not json\n"
			+ json.dumps({"command": "post", "doc": f"discord/{DATE}", "status": "failed"}) + "\n"
			+ json.dumps({"command": "sync", "doc": f"discord/{DATE}", "status": "posted"}) + "\n"
			+ json.dumps({"command": "post", "doc": f"slack/{DATE}", "status": "posted"}) + "\n"
			+ "[1, 2]\n",
			encoding="utf-8",
		)
		code, _, opener = self.confirmed()
		self.assertEqual((code, len(opener.requests)), (0, 1))

	def test_failed_send_is_not_recorded_so_the_user_can_retry_deliberately(self):
		self.set_webhook()
		self.write_message()
		code, _, _ = self.confirmed(opener=FakeOpener(http_error(500)))
		self.assertEqual(code, 1)
		self.assertEqual(self.audit_lines(), [])


class FailureTests(PostCase):
	def test_http_error_reports_code_and_server_message_only(self):
		self.set_webhook()
		self.write_message()
		opener = FakeOpener(http_error(400, json.dumps({"message": "Invalid Form Body", "code": 50035}).encode()))
		code, _, opener = self.confirmed(opener=opener)
		self.assertEqual(code, 1)
		self.assertIn("error: HTTP 400: Invalid Form Body", self.last_output)
		self.assert_no_url(self.last_output)
		self.assertEqual(len(opener.requests), 1)

	def test_http_error_without_message_is_just_the_code(self):
		self.set_webhook()
		self.write_message()
		for body in (b"", b"<html>nope</html>", b"[1]", b'{"message": 5}'):
			with self.subTest(body=body):
				code, _, _ = self.confirmed(opener=FakeOpener(http_error(404, body)))
				self.assertEqual(code, 1)
				self.assertTrue(self.last_output.strip().endswith("error: HTTP 404"), self.last_output)

	def test_slack_plain_text_error_code_is_shown(self):
		self.set_webhook("slack")
		self.write_message("slack")
		code, _, _ = self.confirmed("slack", opener=FakeOpener(http_error(404, b"no_service", url=SLACK_URL)))
		self.assertEqual(code, 1)
		self.assertIn("error: HTTP 404: no_service", self.last_output)
		self.assert_no_url(self.last_output)

	def test_server_message_echoing_the_webhook_is_redacted(self):
		self.set_webhook()
		self.write_message()
		leaky = (
			json.dumps({"message": f"Unknown webhook {DISCORD_URL}"}).encode(),
			json.dumps({"message": f"bad token {TOKEN_PART}"}).encode(),
			json.dumps({"message": "token ghp_abcdefghijklmnop"}).encode(),
		)
		for body in leaky:
			with self.subTest(body=body):
				code, _, _ = self.confirmed(opener=FakeOpener(http_error(401, body)))
				self.assertEqual(code, 1)
				self.assertIn("error: HTTP 401: [redacted]", self.last_output)
				self.assert_no_url(self.last_output)
				self.assertNotIn("ghp_", self.last_output)

	def test_long_server_message_is_truncated(self):
		with self.assertRaises(SuiteError) as caught:
			ts_post.post_message(
				DISCORD_URL, "discord", "hi", opener=FakeOpener(http_error(400, json.dumps({"message": "m" * 5000}).encode()))
			)
		self.assertLess(len(str(caught.exception)), 300)

	def test_unreachable_names_the_host_only_and_never_retries(self):
		self.set_webhook()
		self.write_message()
		reason = OSError(f"[Errno -2] Name or service not known {DISCORD_URL}")
		for failure in (urllib.error.URLError(reason), TimeoutError(DISCORD_URL), ConnectionResetError(DISCORD_URL)):
			with self.subTest(type(failure).__name__):
				opener = FakeOpener(failure)
				code, _, opener = self.confirmed(opener=opener)
				self.assertEqual(code, 1)
				self.assertIn("Could not reach discord.com", self.last_output)
				self.assert_no_url(self.last_output)
				self.assertEqual(len(opener.requests), 1)
		self.assertEqual(self.audit_lines(), [])

	def test_exception_chain_does_not_carry_the_url(self):
		with self.assertRaises(SuiteError) as caught:
			ts_post.post_message(DISCORD_URL, "discord", "hi", opener=FakeOpener(urllib.error.URLError(DISCORD_URL)))
		self.assertIsNone(caught.exception.__cause__)
		self.assertTrue(caught.exception.__suppress_context__)
		self.assert_no_url("".join(traceback.format_exception(caught.exception)))

	def test_audit_log_failure_warns_but_the_post_still_succeeds(self):
		self.set_webhook()
		self.write_message()
		with mock.patch.object(ts_post, "AuditLog", side_effect=RuntimeError("disk")):
			code, lines, opener = self.confirmed()
		self.assertEqual(code, 0)
		self.assertEqual(len(opener.requests), 1)
		self.assertTrue(any("audit log" in line for line in lines))


class RedirectTests(PostCase):
	"""A redirect must never be followed: the webhook is a bearer secret and a retried POST would duplicate."""

	def redirecting_opener(self, location: str):
		class Redirector(urllib.request.BaseHandler):
			handler_order = 100
			calls = 0

			def https_open(self, request):
				type(self).calls += 1
				headers = email.message.Message()
				headers["Location"] = location
				response = urllib.response.addinfourl(io.BytesIO(b""), headers, request.full_url, code=307)
				response.msg = "Temporary Redirect"
				return response

		opener = build_opener(origin_of(DISCORD_URL), False)
		opener.add_handler(Redirector())
		return opener, Redirector

	def test_cross_origin_redirect_is_refused_and_not_followed(self):
		self.set_webhook()
		self.write_message()
		opener, handler = self.redirecting_opener("https://evil.example/collect")
		code, _, _ = self.confirmed(opener=opener)
		self.assertEqual(code, 1)
		self.assertEqual(handler.calls, 1)
		self.assertIn("redirect", self.last_output)
		self.assert_no_url(self.last_output)
		self.assertEqual(self.audit_lines(), [])

	def test_same_origin_redirect_is_refused_too(self):
		self.set_webhook()
		self.write_message()
		opener, handler = self.redirecting_opener("https://discord.com/api/webhooks/1/other")
		code, _, _ = self.confirmed(opener=opener)
		self.assertEqual(code, 1)
		self.assertEqual(handler.calls, 1)
		self.assertIn("refusing to follow", self.last_output)
		self.assert_no_url(self.last_output)

	def test_default_opener_is_the_no_redirect_one(self):
		with mock.patch.object(ts_post, "build_opener", wraps=build_opener) as built:
			opener = FakeOpener()
			with mock.patch.object(ts_post.urllib.request, "Request", wraps=ts_post.urllib.request.Request):
				built.return_value = opener
				ts_post.post_message(DISCORD_URL, "discord", "hi")
		built.assert_called_once_with(origin_of(DISCORD_URL), False)


if __name__ == "__main__":
	unittest.main()
