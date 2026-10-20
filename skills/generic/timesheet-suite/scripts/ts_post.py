"""Post an already-built chat message to a Discord or Slack incoming webhook. Dry run by default; never retries.

The webhook URL is a bearer secret: it is read only from DISCORD_WEBHOOK_URL / SLACK_WEBHOOK_URL, validated before
any network call, and never printed, stored, or placed in an error message.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

import ts_chat
from ts_common import (
	Env,
	SuiteError,
	build_opener,
	clean_credential,
	config_dir,
	looks_like_secret,
	origin_of,
	out_dir_for,
	parse_date,
)
from ts_lifecycle import AuditLog, LifecycleError, check_confirmation

TIMEOUT = 30
DETAIL_LIMIT = 200
BODY_LIMIT = 4096
USER_AGENT = "timesheet-suite-post"
CONFIRM_FLAG = "confirm-post"

# target -> (environment variable, allowed hosts, required path prefix, message file suffix)
WEBHOOKS = {
	"discord": (
		"DISCORD_WEBHOOK_URL",
		frozenset({"discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com"}),
		"/api/webhooks/",
		"md",
	),
	"slack": ("SLACK_WEBHOOK_URL", frozenset({"hooks.slack.com"}), "/services/", "txt"),
}


def _unsupported(target: str) -> SuiteError:
	return SuiteError(
		f"Cannot post to {target!r} — only {', '.join(WEBHOOKS)} support posting; "
		"Teams, Gmail and WhatsApp messages are sent by the user from the built files"
	)


def _not_a_webhook(target: str) -> SuiteError:
	return SuiteError(f"The {target} webhook URL is not a {target} webhook - refusing to send")


def validate_webhook(target: str, url: str) -> str:
	"""The webhook's host when `url` is a genuine `target` webhook; otherwise a SuiteError that never echoes `url`."""
	if target not in WEBHOOKS:
		raise _unsupported(target)
	_, hosts, prefix, _ = WEBHOOKS[target]
	try:
		parts = urllib.parse.urlsplit(url)
		host, port = parts.hostname, parts.port
	except ValueError:
		raise _not_a_webhook(target) from None
	if (
		parts.scheme != "https"
		or host is None
		or host.lower() not in hosts
		or port not in (None, 443)
		or parts.username is not None
		or parts.password is not None
		or any(char.isspace() or ord(char) < 0x20 or ord(char) == 0x7F for char in url)
		or not parts.path.startswith(prefix)
		or len(parts.path) == len(prefix)
	):
		raise _not_a_webhook(target)
	return host.lower()


def webhook_from_env(target: str) -> str:
	if target not in WEBHOOKS:
		raise _unsupported(target)
	variable = WEBHOOKS[target][0]
	url = clean_credential(os.environ.get(variable), variable)
	if url is None:
		raise SuiteError(f"No {target} webhook — set {variable} in the environment (it is never a flag)")
	validate_webhook(target, url)
	return url


def payload_for(target: str, text: str) -> dict:
	if target == "discord":
		return {"content": text, "allowed_mentions": {"parse": []}}
	return {"text": text}


def _leaks(message: str, url: str) -> bool:
	"""True when a server-supplied `message` repeats the webhook (or a secret path segment of it) or any known secret."""
	if looks_like_secret(message) or url in message:
		return True
	prefix = next(spec[2] for spec in WEBHOOKS.values() if urllib.parse.urlsplit(url).path.startswith(spec[2]))
	secret_path = urllib.parse.urlsplit(url).path[len(prefix):]
	return any(len(segment) >= 6 and segment in message for segment in secret_path.split("/"))


def _server_detail(body: bytes, target: str, url: str) -> str:
	"""A short, single-line server explanation: the JSON `message` field (Discord/Slack) or a Slack error code."""
	text = body.decode("utf-8", "replace").strip()
	detail = ""
	try:
		data = json.loads(text)
	except ValueError:
		data = None
		if target == "slack" and 0 < len(text) <= 60 and all(char.isalnum() or char in "_ .-" for char in text):
			detail = text
	if isinstance(data, dict) and isinstance(data.get("message"), str):
		detail = data["message"]
	detail = " ".join(detail.split())
	if len(detail) > DETAIL_LIMIT:
		detail = detail[: DETAIL_LIMIT - 1].rstrip() + "…"
	return "[redacted]" if detail and _leaks(detail, url) else detail


def _http_error(exc: urllib.error.HTTPError, target: str, url: str) -> SuiteError:
	try:
		body = exc.read(BODY_LIMIT)
	except Exception:  # noqa: BLE001 - an unreadable error body must not mask the status
		body = b""
	try:
		exc.close()
	except Exception:  # noqa: BLE001
		pass
	detail = _server_detail(body, target, url)
	return SuiteError(f"HTTP {exc.code}" + (f": {detail}" if detail else ""))


def post_message(url: str, target: str, text: str, opener=None, timeout: int = TIMEOUT) -> int:
	"""POST `text` once to the webhook and return the 2xx status. Never retries, follows a redirect, or echoes `url`."""
	host = validate_webhook(target, url)
	if opener is None:
		opener = build_opener(origin_of(url), False)
	body = json.dumps(payload_for(target, text), ensure_ascii=False).encode("utf-8")
	try:
		request = urllib.request.Request(
			url, data=body, method="POST", headers={"Content-Type": "application/json", "User-Agent": USER_AGENT}
		)
		with opener.open(request, timeout=timeout) as response:
			status = getattr(response, "status", None)
			response.read()
	except urllib.error.HTTPError as exc:
		raise _http_error(exc, target, url) from None
	except (urllib.error.URLError, OSError, http.client.HTTPException):
		raise SuiteError(
			f"Could not reach {host}. Nothing is retried automatically; check the channel before posting again"
		) from None
	except ValueError:
		raise SuiteError(f"The {target} request could not be sent — check the message and the webhook for stray characters") from None
	if not isinstance(status, int) or not 200 <= status < 300:
		raise SuiteError(f"HTTP {status}")
	return status


def already_posted(doc: str) -> bool:
	"""True when the audit log records a successful `post` of `doc` (`<target>/<date>`)."""
	try:
		lines = (config_dir() / "audit.log").read_text(encoding="utf-8", errors="replace").splitlines()
	except OSError:
		return False
	for line in lines:
		try:
			record = json.loads(line)
		except ValueError:
			continue
		if (
			isinstance(record, dict)
			and record.get("command") == "post"
			and record.get("doc") == doc
			and record.get("status") == "posted"
		):
			return True
	return False


def _read_message(path: Path, target: str, date: str) -> str:
	try:
		text = path.read_text(encoding="utf-8")
	except FileNotFoundError:
		raise SuiteError(f"No {path.name} in {path.parent} — run `build` for {date} first (with {target} in the chat targets)") from None
	except (OSError, UnicodeDecodeError) as exc:
		raise SuiteError(f"Could not read {path.name}: {getattr(exc, 'strerror', None) or type(exc).__name__}") from None
	text = text.rstrip("\n")
	if not text.strip():
		raise SuiteError(f"{path.name} is empty — run `build` again")
	return text


def cmd_post(args: argparse.Namespace, env: Env) -> int:
	target = str(args.target or "").strip().lower()
	if target not in WEBHOOKS:
		raise _unsupported(target)
	date = parse_date(args.date)
	profile = env.read_profile() or {}
	folder = out_dir_for(profile, args.out_dir)
	spec = ts_chat.TARGETS[target]
	path = folder / ts_chat.chat_filename(target, date, WEBHOOKS[target][3])
	text = _read_message(path, target, date)
	size = ts_chat._measure(text, spec.unit)
	if size > spec.limit:
		raise SuiteError(
			f"{path.name} is {size} {spec.unit}, over the {target} limit of {spec.limit} — run `build` again after shortening it"
		)
	url = webhook_from_env(target)
	host = validate_webhook(target, url)
	doc = f"{target}/{date}"
	confirmed = check_confirmation(CONFIRM_FLAG, doc, {CONFIRM_FLAG: args.confirm_post})
	posted_before = already_posted(doc)

	if not confirmed:
		env.out(f"target: {target}")
		env.out(f"destination: {host}")
		env.out(f"message: {path}")
		env.out(f"size: {size}/{spec.limit} {spec.unit}")
		env.out("first lines:")
		for line in text.splitlines()[:3]:
			env.out(f"  | {line}")
		if posted_before:
			env.out(f"note: {doc} was already posted (audit log); sending again needs --repost")
		env.out(
			f"Dry run - nothing sent. Ask the user in this conversation, then re-run with --{CONFIRM_FLAG} {doc}"
		)
		return 0

	if posted_before and not args.repost:
		raise LifecycleError(
			f"{doc} was already posted (see audit.log). Nothing was sent; ask the user, then add --repost to post it again",
			code="already_posted",
			exit_code=2,
		)
	status = post_message(url, target, text)
	try:
		AuditLog(env.out)(command="post", site=host, doc=doc, status="posted")
	except Exception as exc:  # noqa: BLE001 - the message is already out; a log failure must not look like a failed send
		env.out(f"warning: could not write the audit log ({type(exc).__name__})")
	env.out(f"Posted {doc} to {host} (HTTP {status})")
	return 0


def add_parsers(commands) -> dict[str, Callable[[argparse.Namespace, Env], int]]:
	post = commands.add_parser(
		"post", help="post a built Discord/Slack message to its incoming webhook (dry run by default)", allow_abbrev=False
	)
	post.add_argument("--date", required=True, help="YYYY-MM-DD of the built message")
	post.add_argument("--target", required=True, help="discord or slack (webhook URL comes from DISCORD_WEBHOOK_URL / SLACK_WEBHOOK_URL)")
	post.add_argument("--confirm-post", help="<target>/<date>, the token the dry run printed")
	post.add_argument("--repost", action="store_true", help="post again although the audit log shows it was already posted")
	post.add_argument("--out-dir", help="folder holding the built message (default: the profile's out_dir)")
	return {"post": cmd_post}
