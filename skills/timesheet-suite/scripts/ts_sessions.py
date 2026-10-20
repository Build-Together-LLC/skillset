"""Digest of the day's AI-coding-chat work (Claude Code and OMP transcripts). Stdlib only, read-only.

Imports ts_common only. Transcripts are located under an injectable home directory, filtered by the cwd of each
session (must be at or under one of the configured roots) and by the timestamp of each message (never the file
name or mtime: a file can span days). The result is evidence for the timesheet author: prompts and outcomes,
never hours. Every emitted string is redacted.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Callable, Iterator

from ts_common import (
	DEFAULT_UTC_OFFSET,
	MIN_SECRET_LENGTH,
	SECRET_ENV_VARS,
	SECRET_PREFIX,
	Env,
	SuiteError,
	day_window,
	in_window,
	out_dir_for,
	parse_date,
	parse_timestamp,
	split_list,
	write_private_json,
)

VERSION = 1
NOTE = "estimates only: prompts and outcomes, not hours"
NO_ROOTS = "No session roots - pass --roots or run `profile set --session-roots ...`"
REDACTED = "[redacted]"
PROMPT_LIMIT = 500
OUTCOME_LIMIT = 1500
OUTCOME_MIN = 200
OUTCOMES_KEPT = 6
REPLAY_KEY = 200
SOURCES = (
	("claude", (".claude", "projects")),
	("omp", (".omp", "agent", "sessions")),
)
KEY_SECRET_PAIR = re.compile(r"\b[0-9a-f]{15}:[0-9a-f]{15}\b")
PREFIXED_SECRET = re.compile(SECRET_PREFIX.pattern + r"\S*")

__all__ = ["build_digest", "redact", "resolve_roots", "add_parsers"]


# Text


def _collapse(text: str) -> str:
	return " ".join(text.split())


def redact(text: str) -> str:
	"""Secrets out of one string: a current environment secret blanks the whole text, token shapes just themselves."""
	for name in SECRET_ENV_VARS:
		secret = os.environ.get(name) or ""
		if len(secret) >= MIN_SECRET_LENGTH and secret in text:
			return REDACTED
	return KEY_SECRET_PAIR.sub(REDACTED, PREFIXED_SECRET.sub(REDACTED, text))


def _clip(text: str, limit: int) -> str:
	return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _text_of(content) -> str:
	"""The text blocks of a message joined; tool_use, tool_result, thinking and other blocks are ignored."""
	if isinstance(content, str):
		return content.strip()
	if not isinstance(content, list):
		return ""
	parts = [
		block["text"]
		for block in content
		if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
	]
	return "\n".join(parts).strip()


# Roots


def _norm(path: str) -> str:
	return os.path.abspath(os.path.expanduser(path))


def resolve_roots(arg_roots, profile: dict | None) -> list[str]:
	roots = [_norm(item) for item in split_list(arg_roots or (profile or {}).get("session_roots"))]
	if not roots:
		raise SuiteError(NO_ROOTS)
	return roots


def _under(cwd, roots: list[str]) -> bool:
	if not isinstance(cwd, str) or not cwd:
		return False
	cwd = os.path.abspath(cwd)
	return any(cwd == root or cwd.startswith(root.rstrip(os.sep) + os.sep) for root in roots)


# Transcripts


def _records(path: Path) -> Iterator[dict]:
	"""JSON objects of a transcript; unreadable files and malformed lines yield nothing."""
	try:
		with path.open(encoding="utf-8", errors="replace") as handle:
			for line in handle:
				try:
					record = json.loads(line)
				except ValueError:
					continue
				if isinstance(record, dict):
					yield record
	except OSError:
		return


def _messages(source: str, path: Path) -> Iterator[tuple[str, str, str, str | None]]:
	"""(role, timestamp, text, cwd) of every user/assistant message that carries text."""
	cwd = None
	for record in _records(path):
		kind = record.get("type")
		if source == "omp":
			if kind == "session":
				cwd = record.get("cwd") if cwd is None else cwd
				continue
			if kind != "message":
				continue
		else:
			if kind not in ("user", "assistant") or record.get("isMeta"):
				continue
			cwd = record.get("cwd") or cwd
		message = record.get("message")
		if not isinstance(message, dict):
			continue
		role = message.get("role") if source == "omp" else kind
		if role not in ("user", "assistant"):
			continue
		stamp = record.get("timestamp") or message.get("timestamp")
		text = _text_of(message.get("content"))
		if isinstance(stamp, str) and text:
			yield role, stamp, text, cwd


def _transcripts(home: Path) -> Iterator[tuple[str, Path]]:
	for source, parts in SOURCES:
		base = home.joinpath(*parts)
		if base.is_dir():
			for path in sorted(base.rglob("*.jsonl")):
				if path.is_file():
					yield source, path


def _stamp(value: str):
	try:
		stamp = parse_timestamp(value)
	except (ValueError, TypeError):
		return None
	return stamp if stamp.tzinfo else None


def _replay_key(text: str) -> str:
	return _collapse(text)[:REPLAY_KEY]


def _collect(source: str, path: Path, window, roots: list[str], before: set[str]) -> list[dict]:
	"""Sessions (one per cwd) of one transcript for the window; pre-window prompts are added to `before`."""
	sessions: dict[str, dict] = {}
	for role, value, text, cwd in _messages(source, path):
		stamp = _stamp(value)
		if stamp is None:
			continue
		if stamp < window[0]:
			if role == "user":
				before.add(_replay_key(text))
			continue
		if not in_window(value, window) or not _under(cwd, roots):
			continue
		session = sessions.setdefault(cwd, {"source": source, "path": str(path), "cwd": cwd, "events": []})
		session["events"].append((stamp, role, text))
	return list(sessions.values())


def _finish(raw: dict, before: set[str], tz) -> dict | None:
	"""One session's prompts and outcomes; None when nothing human or substantial is left (only system noise)."""
	prompts, outcomes = [], []
	for stamp, role, text in sorted(raw["events"], key=lambda event: event[0]):
		flat = _collapse(text)
		at = stamp.astimezone(tz).isoformat(timespec="seconds")
		if role == "user":
			if flat and not text.startswith("<") and _replay_key(text) not in before:
				prompts.append({"at": at, "stamp": stamp, "text": _clip(redact(flat), PROMPT_LIMIT)})
		elif len(flat) >= OUTCOME_MIN:
			outcomes.append({"at": at, "stamp": stamp, "text": _clip(redact(flat), OUTCOME_LIMIT)})
	if not prompts and not outcomes:
		return None
	outcomes = outcomes[-OUTCOMES_KEPT:]
	stamps = [item["stamp"] for item in prompts + outcomes]
	first, last = min(stamps), max(stamps)
	return {
		"source": raw["source"],
		"path": redact(raw["path"]),
		"cwd": redact(raw["cwd"]),
		"first_at": first.astimezone(tz).isoformat(timespec="seconds"),
		"last_at": last.astimezone(tz).isoformat(timespec="seconds"),
		"prompts": [{"at": item["at"], "text": item["text"]} for item in prompts],
		"outcomes": [{"at": item["at"], "text": item["text"]} for item in outcomes],
	}


def build_sessions(date: str, roots: list[str], utc_offset: str, home: Path | None = None) -> list[dict]:
	window = day_window(date, utc_offset)
	tz = window[0].tzinfo
	home = Path(home) if home is not None else Path.home()
	before: set[str] = set()
	raws: list[dict] = []
	old_files: list[tuple[str, Path]] = []
	for source, path in _transcripts(home):
		try:
			fresh = path.stat().st_mtime >= window[0].timestamp()
		except OSError:
			continue
		if fresh:
			raws.extend(_collect(source, path, window, roots, before))
		else:
			old_files.append((source, path))
	if raws:
		# Replays are only detectable against the original history, which lives in files untouched since.
		for source, path in old_files:
			for role, value, text, _cwd in _messages(source, path):
				stamp = _stamp(value)
				if role == "user" and stamp is not None and stamp < window[0]:
					before.add(_replay_key(text))
	sessions = [session for raw in raws if (session := _finish(raw, before, tz))]
	sessions.sort(key=lambda session: (session["first_at"], session["source"], session["path"]))
	return sessions


def build_digest(date: str, roots: list[str], utc_offset: str, home: Path | None = None) -> dict:
	return {
		"version": VERSION,
		"date": date,
		"utc_offset": utc_offset,
		"roots": [redact(root) for root in roots],
		"sessions": build_sessions(date, roots, utc_offset, home),
		"note": NOTE,
	}


# CLI


def home_dir() -> Path:
	return Path.home()


def add_parsers(commands) -> dict[str, Callable[[argparse.Namespace, Env], int]]:
	sessions = commands.add_parser(
		"sessions", help="optional: digest of the day's AI-coding-chat work (Claude Code, OMP)", allow_abbrev=False
	)
	sessions.add_argument("--date", required=True, help="YYYY-MM-DD")
	sessions.add_argument("--roots", help="comma-separated project folders (default: profile session_roots)")
	sessions.add_argument("--utc-offset", help=f"offset the day is read in (default: profile utc_offset, then {DEFAULT_UTC_OFFSET})")
	sessions.add_argument("--out", help="output folder (default: the profile out_dir); the file is sessions_<date>.json")
	return {"sessions": cmd_sessions}


def cmd_sessions(args: argparse.Namespace, env: Env) -> int:
	profile = env.read_profile() or {}
	date = parse_date(args.date)
	roots = resolve_roots(args.roots, profile)
	offset = args.utc_offset or profile.get("utc_offset") or DEFAULT_UTC_OFFSET
	digest = build_digest(date, roots, offset, home_dir())
	path = out_dir_for(profile, args.out) / f"sessions_{date}.json"
	write_private_json(path, digest)
	env.out(f"wrote {path}")
	for session in digest["sessions"]:
		env.out(
			f"{session['source']} {session['cwd']} {session['first_at'][11:16]}-{session['last_at'][11:16]} "
			f"prompts {len(session['prompts'])} outcomes {len(session['outcomes'])}"
		)
	if not digest["sessions"]:
		env.out(f"warning: no sessions found in {', '.join(digest['roots'])} for {date}")
	return 0
