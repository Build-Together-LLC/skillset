"""Unit tests for ts_chat.py (chat targets, renderers, ladder). Run from the skill folder:

    python3 -m unittest discover -s scripts -p 'test_ts_chat*.py'
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ts_chat  # noqa: E402
import ts_common  # noqa: E402
from ts_testkit import entry  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "assets"
DATE = "2026-09-08"
ALL = ts_chat.TARGET_NAMES


def ticket(key="EXM-1", title="Invoice export", status="In Progress", url=None):
	return {
		"label": key,
		"url": url or f"https://example.atlassian.net/browse/{key}",
		"kind": "ticket",
		"title": title,
		"status": status,
	}


def text_of(target, entries, hours=None, **kwargs):
	"""The primary message of one target."""
	rendered = ts_chat.render(target, DATE, entries, hours or [1.0] * len(entries), **kwargs)
	return rendered.files[next(iter(rendered.files))]


# Frozen copy of the pre-v2 render_discord (timesheet_suite.py / ts_chat seed). Do not edit: it is the oracle.
def _legacy_render_discord(date, entries, hours, limit=2000):
	def fmt(h):
		return f"{round(h, 2):g}"

	links = [[link for link in entry.get("links") or [] if link.get("url")] for entry in entries]
	embedded = [[True] * len(row) for row in links]

	def render():
		day = dt.date.fromisoformat(date)
		lines = [f"Today's ({day:%b} {day.day}) Update:"]
		for number, (entry, row_links, row_flags, row_hours) in enumerate(
			zip(entries, links, embedded, hours), 1
		):
			label = entry.get("label") or entry.get("activity_type")
			summary = str(entry.get("summary") or entry.get("description") or "").strip()
			text = f"{number}. {label}: {summary}".rstrip()
			refs = [
				f"[{link.get('label') or 'link'}]({link['url']})" if flag else (link.get("label") or "link")
				for link, flag in zip(row_links, row_flags)
			]
			if refs:
				text += " Ref " + ", ".join(refs)
			lines.append(f"{text} ({fmt(row_hours)}h)")
		return "\n".join(lines)

	message = render()
	positions = [(row, col) for row in range(len(links)) for col in range(len(links[row]))]
	for row, col in reversed(positions):
		if len(message) <= limit:
			break
		embedded[row][col] = False
		message = render()
	if len(message) > limit:
		raise ts_common.SuiteError(
			f"Discord update is {len(message)} characters even without embedded links — "
			f"shorten the summaries by at least {len(message) - limit} characters"
		)
	return message, sum(flag for row in embedded for flag in row), len(positions)


def _discord_tuple(entries, hours):
	rendered = ts_chat.render("discord", DATE, entries, hours)
	return rendered.files["md"], rendered.embedded, rendered.links


class DiscordLegacyTests(unittest.TestCase):
	"""The three pre-v2 DiscordTests, now through the generic renderer; assertions unchanged."""

	def test_format_matches_the_daily_update(self):
		entries = [
			entry(
				label="Code Review",
				activity_type="Code review",
				summary="Reviewed PR-1",
				links=[
					{"label": "PR-1", "url": "https://example.com/1"},
					{"label": "PR-2", "url": "https://example.com/2"},
				],
			),
			entry(label="Meeting", activity_type="Meeting", summary="Standup"),
		]
		message, embedded, total = _discord_tuple(entries, [0.5, 0.75])
		self.assertEqual(
			message,
			"Today's (Sep 8) Update:\n"
			"1. Code Review: Reviewed PR-1 Ref [PR-1](https://example.com/1), [PR-2](https://example.com/2) (0.5h)\n"
			"2. Meeting: Standup (0.75h)",
		)
		self.assertEqual((embedded, total), (2, 2))

	def test_links_fall_back_to_plain_labels_from_the_end_to_fit(self):
		long_url = "https://example.com/" + "x" * 400
		entries = [entry(summary="Work", links=[{"label": f"L{i}", "url": long_url}]) for i in range(6)]
		message, embedded, total = _discord_tuple(entries, [1.0] * 6)
		self.assertLessEqual(len(message), ts_chat.DISCORD_LIMIT)
		self.assertEqual(total, 6)
		self.assertTrue(0 < embedded < 6)
		self.assertIn("[L0](", message)
		self.assertIn("Ref L5 (1h)", message)

	def test_raises_when_summaries_alone_are_too_long(self):
		entries = [entry(summary="y" * 700) for _ in range(3)]
		with self.assertRaisesRegex(ts_common.SuiteError, "shorten the summaries"):
			ts_chat.render("discord", DATE, entries, [1.0] * 3)


class DiscordGoldenTests(unittest.TestCase):
	def fixtures(self):
		long_url = "https://example.com/" + "x" * 400
		sample = json.loads((ASSETS / "sample_spec.json").read_text(encoding="utf-8"))
		return {
			"two links": ([
				entry(label="Review", summary="Reviewed", links=[
					{"label": "PR-1", "url": "https://example.com/1"},
					{"label": "PR-2", "url": "https://example.com/2"},
				]),
				entry(label="Meeting", summary="Standup"),
			], [0.5, 0.75]),
			"six long links": ([entry(summary="Work", links=[{"label": f"L{i}", "url": long_url}]) for i in range(6)], [1.0] * 6),
			"no links": ([entry(summary=f"Row {i}") for i in range(5)], [0.25, 1, 1.5, 2, 3.333]),
			"commas and fallbacks": ([
				entry(label=None, activity_type="Coding", summary="", description=" Only a description ",
					links=[{"label": "a, b", "url": "https://example.com/a"}, {"url": "https://example.com/b"}, {"label": "gone"}]),
			], [0.75]),
			"many rows": ([
				entry(summary="s" * 90, links=[{"label": f"PR-{i}", "url": f"https://example.com/pull/{i}" + "z" * 60}])
				for i in range(14)
			], [1.0] * 14),
			"sample spec": (sample["entries"], [row["hours"] for row in sample["entries"]]),
		}

	def test_discord_output_equals_the_frozen_legacy_renderer(self):
		for name, (entries, hours) in self.fixtures().items():
			with self.subTest(name):
				self.assertEqual(_discord_tuple(entries, hours), _legacy_render_discord(DATE, entries, hours))

	def test_discord_overflow_error_text_equals_legacy(self):
		entries = [entry(summary="y" * 700) for _ in range(3)]
		with self.assertRaises(ts_common.SuiteError) as legacy:
			_legacy_render_discord(DATE, entries, [1.0] * 3)
		with self.assertRaises(ts_common.SuiteError) as new:
			ts_chat.render("discord", DATE, entries, [1.0] * 3)
		self.assertEqual(str(new.exception), str(legacy.exception))

	def test_discord_equals_the_committed_sample_update(self):
		sample = json.loads((ASSETS / "sample_spec.json").read_text(encoding="utf-8"))
		doc = (ASSETS / "sample_discord_update.md").read_text(encoding="utf-8")
		expected = doc.split("\n---\n")[1].strip()
		hours = [row["hours"] for row in sample["entries"]]
		rendered = ts_chat.render("discord", sample["date"], sample["entries"], hours)
		self.assertEqual(rendered.files["md"], expected)


class SampleAssetTests(unittest.TestCase):
	def test_samples_equal_a_fresh_render(self):
		names = sorted(ASSETS.glob("sample_chat_*"))
		self.assertTrue(names)
		for path in names:
			match = re.fullmatch(r"sample_chat_([a-z]+?)(_jira)?\.(\w+)", path.name)
			self.assertTrue(match, path.name)
			target, jira, suffix = match.groups()
			spec = json.loads((ASSETS / ("sample_spec_jira.json" if jira else "sample_spec.json")).read_text(encoding="utf-8"))
			hours = [row["hours"] for row in spec["entries"]]
			rendered = ts_chat.render(target, spec["date"], spec["entries"], hours, employee_name="Example Employee")
			expected = rendered.files[suffix]
			expected = expected if expected.endswith("\n") else expected + "\n"
			with self.subTest(path.name):
				self.assertEqual(path.read_text(encoding="utf-8"), expected)


class LadderTests(unittest.TestCase):
	def test_ticket_title_is_dropped_before_any_link_is_unembedded(self):
		url = "https://example.atlassian.net/browse/EXM-{n}?" + "q" * 200
		entries = [
			entry(summary="Work", links=[ticket(f"EXM-{n}", title=f"Title number {n} " + "t" * 50, url=url.format(n=n))])
			for n in range(6)
		]
		rendered = ts_chat.render("discord", DATE, entries, [1.0] * 6)
		message = rendered.files["md"]
		self.assertLessEqual(len(message), 2000)
		self.assertEqual((rendered.embedded, rendered.links), (6, 6))
		rows = message.splitlines()[1:]
		self.assertNotIn("Title number 5", rows[-1])
		self.assertIn("Title number 0", rows[0])

	def test_whatsapp_keeps_raw_urls_then_degrades_to_labels(self):
		url = "https://example.com/" + "x" * 300
		entries = [entry(summary="Work", links=[{"label": f"L{i}", "url": url}]) for i in range(14)]
		rendered = ts_chat.render("whatsapp", DATE, entries, [1.0] * 14)
		message = rendered.files["txt"]
		self.assertLessEqual(len(message.encode("utf-16-le")) // 2, 4096)
		self.assertIn(f"L0 {url}", message)
		self.assertTrue(message.splitlines()[-1].endswith("Ref L13 (1h)"))
		self.assertTrue(message.startswith("*Today's (Sep 8) Update:*\n"))
		self.assertTrue(0 < rendered.embedded < 14)

	def test_render_all_reports_every_failing_target_and_returns_nothing(self):
		entries = [entry(summary="y" * 2100), entry(summary="z" * 2100)]
		with self.assertRaises(ts_common.SuiteError) as caught:
			ts_chat.render_all(["discord", "teams", "slack"], DATE, entries, [1.0, 1.0])
		message = str(caught.exception)
		self.assertIn("Discord update is", message)
		self.assertIn("Slack update is", message)
		self.assertNotIn("Teams", message)
		self.assertRegex(message, r"by at least \d+ characters")
		self.assertEqual(len(message.splitlines()), 2)

	def test_render_all_renders_every_target_in_order(self):
		entries = [entry(summary="Fine", links=[{"label": "PR", "url": "https://example.com/1"}])]
		result = ts_chat.render_all(["slack", "gmail"], DATE, entries, [1.0], employee_name="Ada")
		self.assertEqual(list(result), ["slack", "gmail"])
		self.assertEqual(result["gmail"].subject, "Daily update — Sep 8 — Ada")

	def test_utf16_counts_astral_emoji_twice_on_slack(self):
		entries = [entry(summary="🎉" * 2100)]
		with self.assertRaisesRegex(ts_common.SuiteError, "Slack update is"):
			ts_chat.render("slack", DATE, entries, [1.0])
		ts_chat.render("slack", DATE, [entry(summary="🎉" * 1500)], [1.0])

	def test_lone_surrogate_is_replaced_not_a_traceback(self):
		message = text_of("teams", [entry(summary="bad \ud83d here")])
		self.assertIn("bad \ufffd here", message)


class SyntaxTests(unittest.TestCase):
	def test_slack_link_syntax_and_entity_escaping(self):
		entries = [entry(summary="Fix a<b & c>d", links=[{"label": "A|B", "url": "https://example.com/?a=1&b=2"}])]
		message = text_of("slack", entries)
		self.assertTrue(message.startswith("*Today's (Sep 8) Update:*\n"))
		self.assertIn("Fix a&lt;b &amp; c&gt;d", message)
		self.assertIn("<https://example.com/?a=1&amp;b=2|A¦B>", message)

	def test_teams_card_limit_counts_bytes_of_the_json_file(self):
		entries = [entry(summary="é€" * 4500, links=[{"label": "PR", "url": "https://example.com/1"}])]
		rendered = ts_chat.render("teams", DATE, entries, [1.0])
		raw = rendered.files["json"]
		self.assertLessEqual(len(raw.encode("utf-8")), 28000)
		self.assertLess(len(raw), len(raw.encode("utf-8")))
		card = json.loads(raw)
		body = card["attachments"][0]["content"]["body"][0]
		self.assertEqual(card["attachments"][0]["contentType"], "application/vnd.microsoft.card.adaptive")
		self.assertEqual(body["text"], rendered.files["md"])
		self.assertTrue(body["text"].startswith("**Today's (Sep 8) Update:**\n\n1. Coding: "))
		with self.assertRaisesRegex(ts_common.SuiteError, r"Teams update is \d+ bytes"):
			ts_chat.render("teams", DATE, [entry(summary="é€" * 7000)], [1.0])

	def test_gmail_html_is_escaped_numbered_once_and_has_a_plain_twin(self):
		entries = [
			entry(summary='<script>alert("x")</script> & more', links=[
				ticket("EXM-9", title="<b>bold</b>", url='https://example.com/a?x="1"&y=2'),
			])
		]
		rendered = ts_chat.render("gmail", DATE, entries, [2.0], employee_name="N" * 120)
		html_text, plain = rendered.files["html"], rendered.files["txt"]
		self.assertIn('<meta charset="utf-8">', html_text)
		self.assertNotIn("<script>", html_text)
		self.assertNotIn("<b>bold", html_text)
		self.assertIn('href="https://example.com/a?x=&quot;1&quot;&amp;y=2"', html_text)
		self.assertEqual(html_text.count("1. Coding"), 1)
		self.assertNotIn("<ol", html_text)
		self.assertTrue(plain.startswith(f"Subject: {rendered.subject}\n\n"))
		self.assertIn("EXM-9 <https://example.com/a?x=\"1\"&y=2>", plain)
		self.assertIn("<script>", plain)
		self.assertTrue(rendered.subject.startswith("Daily update — Sep 8 — NNN"))

	def test_gmail_has_one_limit_html_bytes(self):
		ok = ts_chat.render("gmail", DATE, [entry(summary="a" * 30000)], [1.0])
		self.assertGreater(len(ok.files["txt"]), 20000)
		with self.assertRaisesRegex(ts_common.SuiteError, r"Gmail update is \d+ bytes"):
			ts_chat.render("gmail", DATE, [entry(summary="&" * 21000)], [1.0])


class SafetyTests(unittest.TestCase):
	def test_unsupported_url_schemes_are_never_linked_on_any_target(self):
		entries = [entry(summary="Work", links=[
			{"label": "bad", "url": "javascript:alert(1)"},
			{"label": "data", "url": "data:text/html;base64,AAAA"},
			{"label": "ok", "url": "https://example.com/ok"},
		])]
		for target in ALL:
			rendered = ts_chat.render(target, DATE, entries, [1.0])
			joined = "\n".join(rendered.files.values())
			with self.subTest(target):
				self.assertNotIn("javascript:", joined)
				self.assertNotIn("data:text", joined)
				self.assertIn("https://example.com/ok", joined)
				self.assertEqual((rendered.embedded, rendered.links), (1, 3))
				self.assertEqual(len(rendered.warnings), 2)

	def test_link_structure_in_untrusted_text_is_neutralised_everywhere(self):
		evil = "x](http://evil.example/p) *a* [y](http://evil2.example)"
		entries = [entry(label="Lbl [z](http://evil3.example)", summary=evil, links=[
			{"label": "PR [q](http://evil4.example)", "url": "https://example.com/1"},
			ticket("EXM-1", title=evil, status="[s](http://evil5.example)"),
		])]
		allowed = {"https://example.com/1", "https://example.atlassian.net/browse/EXM-1"}
		for target in ALL:
			rendered = ts_chat.render(target, DATE, entries, [1.0])
			with self.subTest(target):
				for content in rendered.files.values():
					self.assertTrue(set(re.findall(r"\]\(([^)]*)\)", content)) <= allowed, content)
					self.assertNotRegex(content, r"\[[^\]]*\]\(http://evil")

	def test_untrusted_newlines_cannot_forge_rows_or_reference_definitions(self):
		forged = "x\n3. FAKE ROW [a][b]\n\n[b]: https://evil.example/p\u2028\u0085[c]: https://evil2.example"
		entries = [entry(label="L\n[d]: https://evil3.example", summary=forged, links=[
			{"label": "PR\n[e]: https://evil4.example", "url": "https://example.com/1"},
			ticket("EXM-1", title="t\n[f]: https://evil5.example", status="s\r\n9. FAKE"),
		])]
		for target in ALL:
			rendered = ts_chat.render(target, DATE, entries, [1.0])
			with self.subTest(target):
				for suffix, content in rendered.files.items():
					if suffix == "json":
						content = json.loads(content)["attachments"][0]["content"]["body"][0]["text"]
					body = content.split("\n\n", 1)[-1] if target == "gmail" and suffix == "txt" else content
					self.assertNotRegex(body, r"\[[^\]]*\](?!\()")  # only real inline links `[x](url)` may remain
					self.assertNotIn("][", body)
					self.assertNotRegex(body, r"(?m)^\s*\d+\. FAKE")
					self.assertNotRegex(body, r"(?m)^\s*\[")
					if suffix != "html":
						self.assertEqual(len([line for line in body.splitlines() if re.match(r"\d+\. ", line)]), 1)

	def test_invisible_and_bidi_characters_in_urls_are_percent_encoded(self):
		url = "https://example.com/a\u202eb\u2028c\u2029d\u200be\u00a0f\x00g\u00e9"
		entries = [entry(summary="Work", links=[{"label": "x", "url": url}])]
		for target in ALL:
			rendered = ts_chat.render(target, DATE, entries, [1.0])
			with self.subTest(target):
				joined = "\n".join(rendered.files.values())
				for bad in ("\u202e", "\u2028", "\u2029", "\u200b", "\u00a0", "\x00"):
					self.assertNotIn(bad, joined)
				self.assertIn("a%E2%80%AEb%E2%80%A8c%E2%80%A9d%E2%80%8Be%C2%A0f%00g\u00e9", joined.replace("&amp;", "&"))

	def test_mentions_are_defanged_and_other_text_is_untouched(self):
		summary = "ping @everyone @here <@123> <!channel> <#99> and user@example.com"
		for target in ALL:
			message = "\n".join(ts_chat.render(target, DATE, [entry(summary=summary)], [1.0]).files.values())
			with self.subTest(target):
				self.assertNotIn("@everyone", message)
				self.assertNotIn("@here", message)
				self.assertNotRegex(message, r"<[@!#](?!doctype)")
				self.assertIn("user@example.com", message)
		self.assertIn("plain text, no mentions", text_of("discord", [entry(summary="plain text, no mentions")]))

	def test_urls_are_percent_encoded_only_where_needed(self):
		plain = "https://example.com/a/b?c=d&e=f#g"
		entries = [entry(summary="Work", links=[
			{"label": "wiki", "url": "https://en.wikipedia.org/wiki/Foo_(bar)"},
			{"label": "sp", "url": "https://example.com/a b\nc\t<x>"},
			{"label": "plain", "url": plain},
		])]
		for target in ("discord", "teams"):
			message = text_of(target, entries)
			with self.subTest(target):
				self.assertIn("[wiki](https://en.wikipedia.org/wiki/Foo_%28bar%29)", message)
				self.assertIn("[sp](https://example.com/a%20b%0Ac%09%3Cx%3E)", message)
				self.assertIn(f"[plain]({plain})", message)
				self.assertEqual(len(message.splitlines()), 2 if target == "discord" else 3)
		self.assertIn("sp https://example.com/a%20b%0Ac%09%3Cx%3E", text_of("whatsapp", entries))

	def test_rows_without_links_and_unicode_labels(self):
		entries = [entry(label="Código ✓", summary="Resumen — listo", links=[{"label": "x"}, {}])]
		message = text_of("discord", entries)
		self.assertEqual(message, "Today's (Sep 8) Update:\n1. Código ✓: Resumen — listo (1h)")


class TargetNameTests(unittest.TestCase):
	def test_normalise_targets_aliases_dedupe_and_unknown(self):
		self.assertEqual(ts_chat.normalise_targets("Email, Microsoft Teams, discord, gmail, msteams"), ["gmail", "teams", "discord"])
		self.assertEqual(ts_chat.normalise_targets(["Slack", "slack"]), ["slack"])
		self.assertIsNone(ts_chat.normalise_targets(None))
		self.assertEqual(ts_chat.normalise_targets("none"), [])
		self.assertEqual(ts_chat.normalise_targets([]), [])
		with self.assertRaises(ts_common.SuiteError) as caught:
			ts_chat.normalise_targets("slak")
		self.assertIn("slack", str(caught.exception))
		secret = "https://hooks.slack.com/services/T000/B000/SECRETSECRETSECRET"
		with self.assertRaises(ts_common.SuiteError) as caught:
			ts_chat.normalise_targets(secret)
		self.assertNotIn("SECRET", str(caught.exception))
		with self.assertRaises(ts_common.SuiteError) as caught:
			ts_chat.normalise_targets("x" * 200)
		self.assertLess(len(str(caught.exception)), 250)

	def test_blank_string_never_clears_but_none_does(self):
		self.assertEqual(ts_chat.resolve_target_change(["slack"], set_="")[0], ["slack"])
		self.assertEqual(ts_chat.resolve_target_change(["slack"], set_="none")[0], [])
		self.assertEqual(ts_chat.resolve_target_change(["slack"], set_=" ")[0], ["slack"])

	def test_resolve_target_change_semantics(self):
		self.assertEqual(ts_chat.resolve_target_change(None, set_="discord,slack"), (["discord", "slack"], []))
		self.assertEqual(ts_chat.resolve_target_change(["discord"], add="slack,discord"), (["discord", "slack"], ["discord was already saved"]))
		self.assertEqual(ts_chat.resolve_target_change(["discord"], remove="teams,discord"), ([], ["teams was not saved"]))
		self.assertEqual(ts_chat.resolve_target_change(None, add="email"), (["gmail"], []))
		self.assertIsNone(ts_chat.resolve_target_change(None)[0])
		self.assertEqual(ts_chat.resolve_target_change(["slack"])[0], ["slack"])
		with self.assertRaisesRegex(ts_common.SuiteError, "alone"):
			ts_chat.resolve_target_change(["discord"], set_="slack", add="teams")


class WriteChatTests(unittest.TestCase):
	def test_write_chat_names_files_per_target_and_is_idempotent(self):
		entries = [entry(summary="Done", links=[{"label": "PR", "url": "https://example.com/1"}])]
		rendered = ts_chat.render_all(list(ALL), DATE, entries, [1.0], employee_name="Ada")
		with tempfile.TemporaryDirectory() as tmp:
			out = Path(tmp) / "nested" / "out"
			paths = ts_chat.write_chat(out, DATE, rendered)
			first = {path.name: path.read_bytes() for path in paths}
			self.assertEqual(
				sorted(first),
				sorted([
					f"discord_{DATE}.md",
					f"chat_slack_{DATE}.txt",
					f"chat_teams_{DATE}.md",
					f"chat_teams_{DATE}.json",
					f"chat_gmail_{DATE}.html",
					f"chat_gmail_{DATE}.txt",
					f"chat_whatsapp_{DATE}.txt",
				]),
			)
			self.assertEqual(sorted(path.name for path in out.iterdir()), sorted(first))
			self.assertTrue(all(data.endswith(b"\n") and not data.endswith(b"\n\n") for data in first.values()))
			self.assertEqual(
				(out / f"discord_{DATE}.md").read_text(encoding="utf-8"),
				rendered["discord"].files["md"] + "\n",
			)
			self.assertEqual({path.name: path.read_bytes() for path in ts_chat.write_chat(out, DATE, rendered)}, first)

	def test_write_chat_files_are_private_and_an_existing_dir_keeps_its_mode(self):
		rendered = ts_chat.render_all(["discord", "teams"], DATE, [entry(summary="Done")], [1.0])
		with tempfile.TemporaryDirectory() as tmp:
			existing = Path(tmp) / "existing"
			existing.mkdir(mode=0o755)
			existing.chmod(0o755)
			paths = ts_chat.write_chat(existing, DATE, rendered)
			self.assertEqual({path.stat().st_mode & 0o777 for path in paths}, {0o600})
			self.assertEqual(existing.stat().st_mode & 0o777, 0o755)
			fresh = Path(tmp) / "a" / "b"
			ts_chat.write_chat(fresh, DATE, rendered)
			self.assertEqual(fresh.stat().st_mode & 0o777, 0o700)
			self.assertEqual([p.name for p in existing.iterdir() if p.name.startswith(".")], [])


if __name__ == "__main__":
	unittest.main()
