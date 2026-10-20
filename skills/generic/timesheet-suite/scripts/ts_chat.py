"""Chat-app targets (Discord, Slack, Teams, Gmail, WhatsApp): names, per-platform renderers, link ladder, files.

Stdlib only; imports ts_common only. Pure except `write_chat`. Nothing here posts anywhere or handles a secret:
the skill WRITES message files and the user pastes/sends them.

Limits and syntax: references/chat_targets.md (sources and retrieval dates).
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, NamedTuple

from ts_common import SuiteError, fmt_hours, looks_like_secret, split_list, write_private_text

DISCORD_LIMIT = 2000
TARGET_NAMES = ("discord", "slack", "teams", "gmail", "whatsapp")
TARGET_ALIASES = {"email": "gmail", "msteams": "teams"}

ZWSP = "\u200b"
TITLE_LIMIT = 80
SUBJECT_NAME_LIMIT = 80
LEVEL_DETAIL, LEVEL_LINK, LEVEL_LABEL = 0, 1, 2  # richest -> poorest rendering of one link


# Target names


def _echo(name: str) -> str:
	"""A user-supplied name for an error message: short, and never a URL or credential (a webhook may be pasted by mistake)."""
	if "://" in name or looks_like_secret(name):
		return "(value hidden)"
	return repr(name if len(name) <= 20 else name[:20] + "…")


def normalise_targets(value) -> list[str] | None:
	"""None stays None (never asked); "none" and [] mean no chat message; aliases resolve; order kept, duplicates dropped."""
	if value is None:
		return None
	names = split_list(value)
	if len(names) == 1 and names[0].lower() == "none" or not names:
		return []
	result: list[str] = []
	for name in names:
		key = " ".join(name.lower().split())
		key = "teams" if key == "microsoft teams" else key
		key = TARGET_ALIASES.get(key, key)
		if key not in TARGET_NAMES:
			raise SuiteError(
				f"Unknown chat target {_echo(name)} — choose from {', '.join(TARGET_NAMES)} "
				"(aliases: email=gmail, msteams=teams)"
			)
		if key not in result:
			result.append(key)
	return result


def _given(value):
	"""A flag value that was really supplied: blank text (an unset shell variable) is 'not given', never 'clear'."""
	return value if value is not None and split_list(value) else None


def resolve_target_change(current, set_=None, add=None, remove=None) -> tuple[list[str] | None, list[str]]:
	"""Apply `--chat-targets` (set_), `--add-chat-targets` (add) and `--remove-chat-targets` (remove) to `current`.

	Returns (new list, notes). `set_` cannot be combined with add/remove. Only the literal `none` clears the list;
	blank values change nothing. With nothing to change, `current` is returned untouched (None stays None).
	"""
	set_, add, remove = _given(set_), _given(add), _given(remove)
	if set_ is not None and (add is not None or remove is not None):
		raise SuiteError("use --chat-targets alone, or --add-chat-targets/--remove-chat-targets")
	if set_ is not None:
		return normalise_targets(set_), []
	added, removed = normalise_targets(add) or [], normalise_targets(remove) or []
	if not added and not removed:
		return (None if current is None else list(current)), []
	result, notes = list(current or []), []
	for target in added:
		if target in result:
			notes.append(f"{target} was already saved")
		else:
			result.append(target)
	for target in removed:
		if target in result:
			result.remove(target)
		else:
			notes.append(f"{target} was not saved")
	return result, notes


# Text hygiene (shared by every target)

_LONE_SURROGATE = re.compile("[\ud800-\udfff]")
_MENTION = re.compile(r"@(?=(?:everyone|here|channel)\b)|<(?=[@!#])")
_HTTP_URL = re.compile(r"https?://[^\s/?#]", re.I)


def _clean(text) -> str:
	"""Lone surrogates -> U+FFFD (they cannot be encoded); @everyone/@here/@channel and <@id> <!x> <#id> defanged."""
	return _MENTION.sub(lambda match: match.group(0) + ZWSP, _LONE_SURROGATE.sub("\ufffd", str(text)))


def _plain(text) -> str:
	"""Untrusted single-line text (summary, labels, Jira title/status): every run of whitespace and line break
	(incl. U+0085, U+2028/9) becomes one space, so it cannot forge a numbered row or a `[x]: url` definition,
	and `[` `]` become `(` `)`, so it can neither form nor close a link."""
	return " ".join(_clean(text).split()).translate(str.maketrans("[]", "()"))


_prose = _plain  # summary and row label get exactly the same treatment as link labels


# Control, format (bidi overrides, ZWSP), line/paragraph separators and space-like characters are never left raw in a URL.
_URL_ENCODE = frozenset({"Cc", "Cf", "Zl", "Zp", "Zs"})


def _percent(url: str, extra: str) -> str:
	url = _LONE_SURROGATE.sub("\ufffd", url)
	return "".join(
		urllib.parse.quote(ch, safe="") if ch in extra or unicodedata.category(ch) in _URL_ENCODE else ch for ch in url
	)


# Per-platform syntax


class _Syntax:
	"""How one platform writes escaped text, link URLs, linked labels, and the refs separator."""

	url_chars = "<>"
	ref_sep = ", "

	def text(self, value: str) -> str:
		return value

	def link_label(self, value: str) -> str:
		return self.text(value)

	def url(self, raw: str) -> str:
		return _percent(raw, self.url_chars)

	def embed(self, label: str, url: str) -> str:
		raise NotImplementedError


class _Markdown(_Syntax):  # Discord and Teams: [label](url)
	url_chars = "()<>"

	def embed(self, label, url):
		return f"[{label}]({url})"


class _Slack(_Syntax):
	url_chars = "|<>"

	def text(self, value):
		return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

	def link_label(self, value):
		return self.text(value).replace("|", "¦")

	def url(self, raw):
		return _percent(raw, self.url_chars).replace("&", "&amp;")

	def embed(self, label, url):
		return f"<{url}|{label}>"


class _WhatsApp(_Syntax):  # no link labels: label + raw URL, auto-linked by the app
	ref_sep = " · "

	def embed(self, label, url):
		return f"{label} {url}"


class _GmailText(_WhatsApp):
	def embed(self, label, url):
		return f"{label} <{url}>"


class _GmailHtml(_Syntax):
	def text(self, value):
		return html.escape(value, quote=False)

	def embed(self, label, url):
		return f'<a href="{html.escape(url, quote=True)}">{label}</a>'


# Rows and the link ladder


class Link(NamedTuple):
	label: str  # already neutralised
	url: str  # raw, stripped
	safe: bool  # http(s) only; anything else is never linked
	detail: str  # "Title (Status)" for Jira tickets, already neutralised; "" otherwise


class Row(NamedTuple):
	number: int
	label: str
	summary: str
	hours: float
	links: list[Link]


class Ctx(NamedTuple):
	date: str
	subject: str | None


class Rendered(NamedTuple):
	files: dict[str, str]  # suffix -> content (no trailing newline); the limited file is `limit_suffix`
	size: int  # measured size of the limited file
	limit: int
	unit: str  # "chars" | "utf16" | "bytes"
	embedded: int  # links not reduced to a bare label
	links: int  # links with a url
	warnings: list[str]
	subject: str | None  # gmail only


def _title(text) -> str:
	text = _plain(text)
	return text if len(text) <= TITLE_LIMIT else text[: TITLE_LIMIT - 1].rstrip() + "…"


def _prepare(entries, hours) -> tuple[list[Row], list[str]]:
	rows, warnings = [], []
	for number, (entry, row_hours) in enumerate(zip(entries, hours), 1):
		links = []
		for link in entry.get("links") or []:
			raw = str(link.get("url") or "").strip()
			if not raw:
				continue
			label = _plain(link.get("label") or "link")
			safe = bool(_HTTP_URL.match(raw))
			if not safe:
				shown = label if len(label) <= 40 else label[:39] + "…"
				warnings.append(f"link {shown!r} skipped: unsupported scheme (only http/https are linked)")
			detail = ""
			if link.get("kind") == "ticket":
				status = _title(link.get("status") or "")
				detail = " ".join(part for part in (_title(link.get("title") or ""), f"({status})" if status else "") if part)
			links.append(Link(label, raw, safe, detail))
		label = entry.get("label") or entry.get("activity_type")
		summary = str(entry.get("summary") or entry.get("description") or "").strip()
		rows.append(Row(number, _prose(label), _prose(summary), row_hours, links))
	return rows, warnings


def _link_text(syntax: _Syntax, link: Link, level: int) -> str:
	label = syntax.link_label(link.label)
	if level == LEVEL_LABEL or not link.safe:
		return label
	text = syntax.embed(label, syntax.url(link.url))
	if level == LEVEL_DETAIL and link.detail:
		text += " " + syntax.text(link.detail)
	return text


def _row_lines(syntax: _Syntax, rows: list[Row], levels: list[list[int]], wrap: Callable[[str], str] = str) -> list[str]:
	lines = []
	for row, row_levels in zip(rows, levels):
		text = f"{row.number}. {syntax.text(row.label)}: {syntax.text(row.summary)}".rstrip()
		refs = [_link_text(syntax, link, level) for link, level in zip(row.links, row_levels)]
		if refs:
			text += " Ref " + syntax.ref_sep.join(refs)
		lines.append(wrap(f"{text} ({fmt_hours(row.hours)}h)"))
	return lines


def _day(date: str) -> str:
	day = dt.date.fromisoformat(date)
	return f"Today's ({day:%b} {day.day}) Update:"


def _build_discord(ctx, rows, levels):
	return {"md": "\n".join([_day(ctx.date)] + _row_lines(_Markdown(), rows, levels))}


def _build_slack(ctx, rows, levels):
	return {"txt": "\n".join([f"*{_day(ctx.date)}*"] + _row_lines(_Slack(), rows, levels))}


def _build_whatsapp(ctx, rows, levels):
	return {"txt": "\n".join([f"*{_day(ctx.date)}*"] + _row_lines(_WhatsApp(), rows, levels))}


def _build_teams(ctx, rows, levels):
	markdown = "\n\n".join([f"**{_day(ctx.date)}**"] + _row_lines(_Markdown(), rows, levels))
	card = {
		"type": "message",
		"attachments": [
			{
				"contentType": "application/vnd.microsoft.card.adaptive",
				"contentUrl": None,
				"content": {
					"$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
					"type": "AdaptiveCard",
					"version": "1.2",
					"body": [{"type": "TextBlock", "text": markdown, "wrap": True}],
				},
			}
		],
	}
	return {"md": markdown, "json": json.dumps(card, ensure_ascii=False, indent=2)}


def _build_gmail(ctx, rows, levels):
	title = html.escape(ctx.subject, quote=False)
	paragraphs = _row_lines(_GmailHtml(), rows, levels, lambda line: f'<p style="margin:0 0 8px">{line}</p>')
	html_doc = "\n".join(
		[
			'<!doctype html><html><head><meta charset="utf-8">' f"<title>{title}</title></head>",
			'<body><div style="font-family:Arial,sans-serif;font-size:14px">',
			f'<p style="margin:0 0 8px"><strong>{html.escape(_day(ctx.date), quote=False)}</strong></p>',
			*paragraphs,
			"</div></body></html>",
		]
	)
	plain = "\n".join([_day(ctx.date)] + _row_lines(_GmailText(), rows, levels))
	return {"html": html_doc, "txt": f"Subject: {ctx.subject}\n\n{plain}"}


@dataclass(frozen=True)
class Target:
	name: str
	label: str
	limit_suffix: str  # which file the limit applies to
	limit: int
	unit: str
	build: Callable[[Ctx, list[Row], list[list[int]]], dict[str, str]]


TARGETS = {
	target.name: target
	for target in (
		Target("discord", "Discord", "md", DISCORD_LIMIT, "chars", _build_discord),
		Target("slack", "Slack", "txt", 4000, "utf16", _build_slack),
		Target("teams", "Teams", "json", 28000, "bytes", _build_teams),
		Target("gmail", "Gmail", "html", 100000, "bytes", _build_gmail),
		Target("whatsapp", "WhatsApp", "txt", 4096, "utf16", _build_whatsapp),
	)
}
assert tuple(TARGETS) == TARGET_NAMES


def _measure(text: str, unit: str) -> int:
	if unit == "chars":
		return len(text)
	if unit == "utf16":
		return len(text.encode("utf-16-le", "surrogatepass")) // 2
	return len(text.encode("utf-8", "replace"))


def _subject(date: str, employee_name) -> str:
	day = dt.date.fromisoformat(date)
	subject = f"Daily update — {day:%b} {day.day}"
	name = " ".join(_LONE_SURROGATE.sub("\ufffd", str(employee_name or "")).split())
	if name:
		name = name if len(name) <= SUBJECT_NAME_LIMIT else name[: SUBJECT_NAME_LIMIT - 1].rstrip() + "…"
		subject += f" — {name}"
	return subject


def render(target: str, date: str, entries: list[dict], hours: list[float], *, employee_name: str = "") -> Rendered:
	"""One message for `target`; links stay embedded only while the limited file fits.

	Ladder (last link first at each stage): drop Jira ticket title/status -> unembed to the bare label -> SuiteError
	naming the exact overflow. Entries, links and hours are never dropped.
	"""
	spec = TARGETS.get(target)
	if spec is None:
		raise SuiteError(f"Unknown chat target {_echo(str(target))} — choose from {', '.join(TARGET_NAMES)}")
	rows, warnings = _prepare(entries, hours)
	levels = [
		[LEVEL_LABEL if not link.safe else LEVEL_DETAIL if link.detail else LEVEL_LINK for link in row.links]
		for row in rows
	]
	ctx = Ctx(date, _subject(date, employee_name) if target == "gmail" else None)
	files = spec.build(ctx, rows, levels)
	size = _measure(files[spec.limit_suffix], spec.unit)
	positions = [(row, col) for row in range(len(rows)) for col in range(len(rows[row].links))]
	for stage in (LEVEL_DETAIL, LEVEL_LINK):
		for row, col in reversed(positions):
			if size <= spec.limit:
				break
			if levels[row][col] == stage:
				levels[row][col] = stage + 1
				files = spec.build(ctx, rows, levels)
				size = _measure(files[spec.limit_suffix], spec.unit)
	if size > spec.limit:
		word = "bytes" if spec.unit == "bytes" else "characters"
		raise SuiteError(
			f"{spec.label} update is {size} {word} even without embedded links — "
			f"shorten the summaries by at least {size - spec.limit} {word}"
		)
	embedded = sum(level != LEVEL_LABEL for row_levels in levels for level in row_levels)
	return Rendered(files, size, spec.limit, spec.unit, embedded, len(positions), warnings, ctx.subject)


def render_all(targets: list[str], date: str, entries: list[dict], hours: list[float], *, employee_name: str = "") -> dict[str, Rendered]:
	"""Render every target; if any overflows, raise ONE SuiteError listing all of them and return nothing."""
	rendered, failures = {}, []
	for target in targets:
		try:
			rendered[target] = render(target, date, entries, hours, employee_name=employee_name)
		except SuiteError as error:
			if target not in TARGETS:
				raise
			failures.append(str(error))
	if failures:
		raise SuiteError("\n".join(failures))
	return rendered


# Files


def chat_filename(target: str, date: str, suffix: str) -> str:
	"""Discord keeps its legacy name `discord_<date>.md`; every other target is `chat_<target>_<date>.<suffix>`."""
	return f"discord_{date}.{suffix}" if target == "discord" else f"chat_{target}_{date}.{suffix}"


def write_chat(out_dir, date: str, rendered: dict[str, Rendered]) -> list[Path]:
	"""Write every file of every rendered target (0600, atomic; overwrites its own earlier output) and return the paths."""
	out_dir = Path(out_dir)
	paths = []
	for target, result in rendered.items():
		for suffix, content in result.files.items():
			path = out_dir / chat_filename(target, date, suffix)
			write_private_text(path, content + "\n")
			paths.append(path)
	return paths


def add_parsers(commands) -> dict:
	"""ts_chat adds no subcommand: chat targets are set with `profile set --chat-targets/--add-chat-targets/...`."""
	return {}
