"""Unit tests for ts_sessions.py (AI-coding-chat digest). Run from the skill folder:

    python3 -m unittest discover -s scripts -p 'test_ts_sessions*.py'
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ts_sessions  # noqa: E402
from ts_common import Env, SuiteError  # noqa: E402

DATE = "2026-09-08"
OFFSET = "+05:30"
# 2026-09-08 00:00 +05:30 == 2026-09-07T18:30Z
TODAY = "2026-09-08T04:00:00Z"
TODAY_LATE = "2026-09-08T09:30:00Z"
YESTERDAY = "2026-09-07T10:00:00Z"
LONG = "Implemented the invoice export end to end and verified it against the sample ledger. " * 4


def write_lines(path: Path, lines: list, mtime: str | None = None) -> Path:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text("\n".join(line if isinstance(line, str) else json.dumps(line) for line in lines) + "\n")
	if mtime:
		stamp = ts_sessions.parse_timestamp(mtime).timestamp()
		os.utime(path, (stamp, stamp))
	return path


def claude(role: str, content, at: str, cwd: str) -> dict:
	return {"type": role, "timestamp": at, "cwd": cwd, "message": {"role": role, "content": content}}


def omp_session(cwd: str) -> dict:
	return {"type": "session", "id": "s1", "timestamp": YESTERDAY, "cwd": cwd}


def omp(role: str, content, at: str) -> dict:
	return {"type": "message", "timestamp": at, "message": {"role": role, "content": content}}


def text(value: str) -> list:
	return [{"type": "text", "text": value}]


class Base(unittest.TestCase):
	def setUp(self):
		tmp = tempfile.TemporaryDirectory()
		self.addCleanup(tmp.cleanup)
		self.tmp = Path(tmp.name)
		self.home = self.tmp / "home"
		self.root = str(self.tmp / "work" / "proj")
		self.claude_dir = self.home / ".claude" / "projects" / "p"
		self.omp_dir = self.home / ".omp" / "agent" / "sessions" / "p"

	def sessions(self, roots=None, date=DATE):
		return ts_sessions.build_sessions(date, roots or [self.root], OFFSET, self.home)


class WindowTests(Base):
	def test_message_timestamp_not_file_name_or_mtime_decides(self):
		write_lines(
			self.claude_dir / "2026-09-07.jsonl",
			[claude("user", "yesterday file, today message", TODAY, self.root)],
			mtime=TODAY,
		)
		write_lines(
			self.claude_dir / "2026-09-08.jsonl",
			[claude("user", "only yesterday inside", YESTERDAY, self.root)],
			mtime=TODAY,
		)
		found = self.sessions()
		self.assertEqual(len(found), 1)
		self.assertTrue(found[0]["path"].endswith("2026-09-07.jsonl"))
		self.assertEqual(found[0]["prompts"][0]["text"], "yesterday file, today message")

	def test_window_edges_use_the_offset(self):
		write_lines(
			self.claude_dir / "a.jsonl",
			[
				claude("user", "before midnight local", "2026-09-07T18:29:59Z", self.root),
				claude("user", "after midnight local", "2026-09-07T18:30:00Z", self.root),
				claude("user", "next day local", "2026-09-08T18:30:00Z", self.root),
			],
			mtime=TODAY_LATE,
		)
		prompts = self.sessions()[0]["prompts"]
		self.assertEqual([p["text"] for p in prompts], ["after midnight local"])
		self.assertEqual(prompts[0]["at"], "2026-09-08T00:00:00+05:30")

	def test_stale_files_are_skipped_by_mtime(self):
		write_lines(
			self.claude_dir / "old.jsonl",
			[claude("user", "claims today but file is ancient", TODAY, self.root)],
			mtime="2026-09-01T00:00:00Z",
		)
		self.assertEqual(self.sessions(), [])


class RootTests(Base):
	def test_descendant_and_exact_match_but_not_siblings(self):
		write_lines(
			self.claude_dir / "a.jsonl",
			[
				claude("user", "exact", TODAY, self.root),
				claude("user", "child", "2026-09-08T05:00:00Z", self.root + "/apps/x"),
				claude("user", "sibling prefix", "2026-09-08T06:00:00Z", self.root + "-other"),
				claude("user", "elsewhere", "2026-09-08T07:00:00Z", "/tmp/elsewhere"),
			],
			mtime=TODAY_LATE,
		)
		found = self.sessions()
		self.assertEqual({s["cwd"]: [p["text"] for p in s["prompts"]] for s in found}, {
			self.root: ["exact"],
			self.root + "/apps/x": ["child"],
		})

	def test_omp_cwd_comes_from_session_record(self):
		write_lines(
			self.omp_dir / "in.jsonl",
			[omp_session(self.root + "/sub"), omp("user", "omp prompt", TODAY)],
			mtime=TODAY_LATE,
		)
		write_lines(
			self.omp_dir / "out.jsonl",
			[omp_session("/somewhere/else"), omp("user", "not mine", TODAY)],
			mtime=TODAY_LATE,
		)
		found = self.sessions()
		self.assertEqual([(s["source"], s["cwd"]) for s in found], [("omp", self.root + "/sub")])

	def test_claude_cwd_can_change_within_a_file(self):
		write_lines(
			self.claude_dir / "a.jsonl",
			[
				claude("user", "outside first", TODAY, "/tmp/elsewhere"),
				claude("user", "then inside", "2026-09-08T05:00:00Z", self.root),
			],
			mtime=TODAY_LATE,
		)
		found = self.sessions()
		self.assertEqual([[p["text"] for p in s["prompts"]] for s in found], [["then inside"]])


class ContentTests(Base):
	def test_tool_blocks_and_system_tags_are_excluded(self):
		write_lines(
			self.claude_dir / "a.jsonl",
			[
				claude("user", "real question", TODAY, self.root),
				claude("user", "<system-reminder>injected</system-reminder>", TODAY, self.root),
				claude("user", "   ", TODAY, self.root),
				claude("user", [{"type": "tool_result", "content": "tool output " + LONG}], TODAY, self.root),
				claude(
					"assistant",
					[{"type": "tool_use", "name": "Bash", "input": {"command": LONG}}, {"type": "text", "text": "short"}],
					TODAY,
					self.root,
				),
				claude("assistant", text(LONG), TODAY_LATE, self.root),
			],
			mtime=TODAY_LATE,
		)
		session = self.sessions()[0]
		self.assertEqual([p["text"] for p in session["prompts"]], ["real question"])
		self.assertEqual(len(session["outcomes"]), 1)
		self.assertNotIn("tool output", json.dumps(session))

	def test_omp_ignores_tool_result_and_developer_roles(self):
		write_lines(
			self.omp_dir / "a.jsonl",
			[
				omp_session(self.root),
				omp("developer", "dev instructions", TODAY),
				omp("toolResult", text(LONG), TODAY),
				omp("user", "human prompt", TODAY),
				omp("assistant", text(LONG), TODAY_LATE),
			],
			mtime=TODAY_LATE,
		)
		session = self.sessions()[0]
		self.assertEqual([p["text"] for p in session["prompts"]], ["human prompt"])
		self.assertEqual(len(session["outcomes"]), 1)

	def test_clipping_collapsing_and_outcome_cap(self):
		lines = [claude("user", "word  " * 300 + "\n\n tail", TODAY, self.root)]
		for number in range(9):
			body = f"outcome {number} " + "x" * 2000
			lines.append(claude("assistant", text(body), f"2026-09-08T0{number}:00:00Z", self.root))
		write_lines(self.claude_dir / "a.jsonl", lines, mtime=TODAY_LATE)
		session = self.sessions()[0]
		prompt = session["prompts"][0]["text"]
		self.assertEqual(len(prompt), 500)
		self.assertNotIn("  ", prompt)
		self.assertEqual(len(session["outcomes"]), 6)
		self.assertTrue(all(len(o["text"]) == 1500 for o in session["outcomes"]))
		self.assertEqual([o["text"].split()[1] for o in session["outcomes"]], ["3", "4", "5", "6", "7", "8"])

	def test_short_assistant_text_is_not_an_outcome(self):
		write_lines(
			self.claude_dir / "a.jsonl",
			[claude("user", "q", TODAY, self.root), claude("assistant", text("Done."), TODAY_LATE, self.root)],
			mtime=TODAY_LATE,
		)
		self.assertEqual(self.sessions()[0]["outcomes"], [])

	def test_malformed_lines_are_skipped(self):
		write_lines(
			self.claude_dir / "a.jsonl",
			["{not json", "[1, 2]", "", claude("user", "survivor", TODAY, self.root), '{"type": "user", "message": 7}'],
			mtime=TODAY_LATE,
		)
		self.assertEqual([p["text"] for p in self.sessions()[0]["prompts"]], ["survivor"])


class ReplayTests(Base):
	def test_resumed_history_is_dropped_whichever_file_holds_the_original(self):
		original = "Please refactor the invoice export module " + "a" * 300
		write_lines(
			self.claude_dir / "orig.jsonl",
			[claude("user", original, YESTERDAY, self.root)],
			mtime=YESTERDAY,
		)
		write_lines(
			self.omp_dir / "resumed.jsonl",
			[
				omp_session(self.root),
				omp("user", original + " (re-stamped, differing tail)", TODAY),
				omp("user", "a genuinely new prompt", TODAY_LATE),
			],
			mtime=TODAY_LATE,
		)
		session = self.sessions()[0]
		self.assertEqual([p["text"] for p in session["prompts"]], ["a genuinely new prompt"])

	def test_same_prompt_twice_today_is_kept(self):
		write_lines(
			self.claude_dir / "a.jsonl",
			[claude("user", "continue", TODAY, self.root), claude("user", "continue", TODAY_LATE, self.root)],
			mtime=TODAY_LATE,
		)
		self.assertEqual(len(self.sessions()[0]["prompts"]), 2)


class RedactionTests(Base):
	TOKENS = (
		"ghp_" + "A1b2C3d4E5f6G7h8I9j0",
		"github_pat_11ABCDEF0_secretsecret",
		"ATATT3xFfGF0fakejiratoken",
		"xoxb-1234-5678-fake",
	)
	PAIR = "0123456789abcde:fedcba987654321"

	def test_no_secret_survives_in_the_written_file(self):
		prompt = " and ".join(self.TOKENS) + f" key {self.PAIR} done"
		write_lines(
			self.claude_dir / "a.jsonl",
			[
				claude("user", prompt, TODAY, self.root),
				claude("assistant", text(LONG + " token " + self.TOKENS[0]), TODAY_LATE, self.root),
			],
			mtime=TODAY_LATE,
		)
		env_secret = "env-secret-value-12345"
		write_lines(
			self.claude_dir / "b.jsonl",
			[claude("user", f"pasted {env_secret} here", TODAY, self.root)],
			mtime=TODAY_LATE,
		)
		out = self.tmp / "out"
		with mock.patch.dict(os.environ, {"FRAPPE_API_SECRET": env_secret}), mock.patch.object(
			ts_sessions, "home_dir", return_value=self.home
		):
			messages: list[str] = []
			env = Env(lambda: {}, lambda: {}, lambda _s: None, messages.append)
			args = argparse.Namespace(date=DATE, roots=self.root, utc_offset=None, out=str(out))
			self.assertEqual(ts_sessions.cmd_sessions(args, env), 0)
		raw = (out / f"sessions_{DATE}.json").read_text()
		for secret in (*self.TOKENS, self.PAIR, env_secret, "A1b2C3d4E5f6G7h8I9j0"):
			self.assertNotIn(secret, raw)
		self.assertIn("[redacted]", raw)
		self.assertNotIn(env_secret, "\n".join(messages))
		prompts = [p["text"] for s in json.loads(raw)["sessions"] for p in s["prompts"]]
		self.assertIn("[redacted]", prompts)  # an env secret blanks the whole message

	def test_redact_keeps_ordinary_text(self):
		self.assertEqual(ts_sessions.redact("ghp_ is a prefix, abc:def stays"), "[redacted] is a prefix, abc:def stays")
		self.assertEqual(ts_sessions.redact("plain text"), "plain text")


class CommandTests(Base):
	def run_cmd(self, roots, profile=None, **overrides):
		out: list[str] = []
		profile = {"out_dir": str(self.tmp / "out"), **(profile or {})}
		env = Env(lambda: profile, lambda: profile, lambda _s: None, out.append)
		args = argparse.Namespace(**{"date": DATE, "roots": roots, "utc_offset": None, "out": None, **overrides})
		with mock.patch.object(ts_sessions, "home_dir", return_value=self.home):
			code = ts_sessions.cmd_sessions(args, env)
		return code, out

	def test_missing_roots_is_an_error(self):
		with self.assertRaises(SuiteError) as caught:
			self.run_cmd(None)
		self.assertEqual(
			str(caught.exception), "No session roots - pass --roots or run `profile set --session-roots ...`"
		)

	def test_profile_roots_are_split_and_tilde_expanded(self):
		roots = ts_sessions.resolve_roots(None, {"session_roots": "~/a, /x/y ,"})
		self.assertEqual(roots, [os.path.expanduser("~/a"), "/x/y"])
		self.assertEqual(ts_sessions.resolve_roots("/p/q", {"session_roots": "/ignored"}), ["/p/q"])

	def test_empty_day_warns_and_still_writes(self):
		code, out = self.run_cmd(self.root)
		self.assertEqual(code, 0)
		self.assertIn(f"warning: no sessions found in {self.root} for {DATE}", out)
		data = json.loads((self.tmp / "out" / f"sessions_{DATE}.json").read_text())
		self.assertEqual(data["sessions"], [])
		self.assertEqual(data["note"], "estimates only: prompts and outcomes, not hours")

	def test_summary_line_and_document_shape(self):
		write_lines(
			self.claude_dir / "a.jsonl",
			[claude("user", "hello", TODAY, self.root), claude("assistant", text(LONG), TODAY_LATE, self.root)],
			mtime=TODAY_LATE,
		)
		code, out = self.run_cmd(self.root, profile={"utc_offset": "+00:00"})
		self.assertEqual(code, 0)
		data = json.loads((self.tmp / "out" / f"sessions_{DATE}.json").read_text())
		self.assertEqual((data["version"], data["date"], data["utc_offset"], data["roots"]), (1, DATE, "+00:00", [self.root]))
		self.assertEqual(set(data["sessions"][0]), {"source", "path", "cwd", "first_at", "last_at", "prompts", "outcomes"})
		self.assertIn(f"claude {self.root} 04:00-09:30 prompts 1 outcomes 1", out)

	def test_reading_leaves_transcripts_untouched(self):
		path = write_lines(self.claude_dir / "a.jsonl", [claude("user", "hi", TODAY, self.root)], mtime=TODAY_LATE)
		before = (path.read_bytes(), path.stat().st_mtime)
		self.run_cmd(self.root)
		self.assertEqual((path.read_bytes(), path.stat().st_mtime), before)


if __name__ == "__main__":
	unittest.main()
