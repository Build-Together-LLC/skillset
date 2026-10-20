#!/usr/bin/env python3
"""Timesheet Suite composition root: `build`, `github`, and the dispatch of every other command.

  build SPEC.json [--out-dir DIR] [--chat-targets CSV] [--jira-digest PATH]
      Writes timesheet_<date>.json (draft Frappe Timesheet) first, then one message per saved chat app
      (discord_<date>.md, chat_<app>_<date>.<ext>), each within that app's limit with links embedded while they fit.
      Exit 2 when no chat apps were ever chosen (the JSON is still written); exit 1 when a message cannot fit.
  github --date YYYY-MM-DD [--users a,b] [--orgs x,y]
      Optional: the day's commits, PRs raised, PRs merged and reviews from GitHub.
  profile | catalogue | jira | sync | update | amend | cancel | submit | pull
      Implemented in ts_profile, ts_catalogue, ts_jira and ts_lifecycle; each module registers its own parsers
      through `add_parsers(commands)` and receives an `Env` (profile loaders, client factory, output).

Safety: stdlib only. Credentials (FRAPPE_*, GITHUB_TOKEN, JIRA_API_TOKEN) come from the environment for a single run
and are never printed or written. Nothing here writes to a Frappe site; that is ts_lifecycle, dry run by default.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import ts_catalogue
import ts_chat
import ts_jira
import ts_lifecycle
import ts_frappe
import ts_post
import ts_profile
import ts_sessions
from ts_common import (
	DEFAULT_UTC_OFFSET,
	Env,
	SuiteError,
	build_opener,
	clean_credential,
	clean_text,
	day_window,
	fmt_hours,
	in_window,
	looks_like_secret,
	normalise_site,
	normalise_time,
	out_dir_for,
	parse_date,
	parse_offset,
	parse_timestamp,
	read_json,
	render_description,
	split_list,
	write_private_json,
	write_private_text,
)

QUARTER_HOUR = 0.25
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
GITHUB_API = "https://api.github.com"
GITHUB_SEARCH_PAGES = 3
CHAT_ASK = (
	"No chat apps saved yet — ask which chat apps to write the daily update for "
	f"({', '.join(ts_chat.TARGET_NAMES)}; one, several, or none), then run "
	"`profile set --chat-targets ...` and build again"
)
ZERO_TOTALS = (
	"total_billable_hours",
	"base_total_billable_amount",
	"base_total_billed_amount",
	"base_total_costing_amount",
	"total_billed_hours",
	"total_billable_amount",
	"total_billed_amount",
	"total_costing_amount",
	"per_billed",
)
ZERO_ROW_AMOUNTS = (
	"billing_hours",
	"base_billing_rate",
	"base_billing_amount",
	"base_costing_rate",
	"base_costing_amount",
	"billing_rate",
	"billing_amount",
	"costing_rate",
	"costing_amount",
)


# Build


def _scale_estimates(entries: list[dict], hours: list[float | None], target: float) -> list[float]:
	"""Fit entries flagged `"estimated": true` to `target`; every other entry keeps the hours it was given.

	Quarter-hour units, largest remainder, at least one quarter per scaled entry, so the total is exact and the
	split follows the original proportions.
	"""
	scaled = [index for index, entry in enumerate(entries) if entry.get("estimated") is True]
	fixed = sum(value for index, value in enumerate(hours) if index not in scaled)
	room = target - fixed
	units = round(room / QUARTER_HOUR)
	if abs(units * QUARTER_HOUR - room) > 1e-6:
		raise SuiteError(
			f"Target {fmt_hours(target)}h minus the fixed {fmt_hours(fixed)}h leaves {fmt_hours(room)}h, "
			"which is not a whole number of quarter hours"
		)
	if units < len(scaled):
		raise SuiteError(
			f"Target {fmt_hours(target)}h leaves {fmt_hours(room)}h for {len(scaled)} estimated entries — too little to split"
		)
	weights = [hours[index] for index in scaled]
	raw = [weight / sum(weights) * units for weight in weights]
	share = [max(1, int(value)) for value in raw]
	gap = units - sum(share)
	while gap > 0:
		pick = max(range(len(scaled)), key=lambda position: raw[position] - share[position])
		share[pick] += 1
		gap -= 1
	while gap < 0:
		pick = max((p for p in range(len(scaled)) if share[p] > 1), key=lambda p: share[p] - raw[p])
		share[pick] -= 1
		gap += 1
	result = [float(value) for value in hours]
	for position, index in enumerate(scaled):
		result[index] = share[position] * QUARTER_HOUR
	return result


def resolve_hours(entries: list[dict], target: float | None) -> list[float]:
	hours: list[float | None] = []
	for index, entry in enumerate(entries, 1):
		value = entry.get("hours")
		if value is not None and float(value) <= 0:
			raise SuiteError(f"Entry {index}: hours must be greater than zero")
		hours.append(None if value is None else float(value))

	pending = [index for index, value in enumerate(hours) if value is None]
	known = sum(value for value in hours if value is not None)
	estimated = [entry.get("estimated") is True for entry in entries]
	if not pending:
		if target is not None and abs(known - float(target)) > 1e-6:
			if any(estimated):
				return _scale_estimates(entries, hours, float(target))
			raise SuiteError(
				f"Entries add up to {fmt_hours(known)}h but the target is {fmt_hours(float(target))}h — "
				'mark the entries whose hours are only estimates with "estimated": true to let the target scale them'
			)
		return [float(value) for value in hours]
	if any(estimated):
		raise SuiteError('"estimated" hours cannot be combined with entries that have no hours — give every entry hours')
	if target is None:
		raise SuiteError(
			"Some entries have no hours — estimate them, or set target_total_hours to split the remainder"
		)

	remainder = float(target) - known
	share = int(round(remainder / len(pending) / QUARTER_HOUR, 9)) * QUARTER_HOUR
	last = round(remainder - share * (len(pending) - 1), 2)
	if last <= 0 or (len(pending) > 1 and share <= 0):
		raise SuiteError(
			f"Target {fmt_hours(float(target))}h leaves {fmt_hours(remainder)}h for "
			f"{len(pending)} entries without hours — too little to split"
		)
	for position, index in enumerate(pending):
		hours[index] = share if position < len(pending) - 1 else last
	return [float(value) for value in hours]


def schedule(date: str, start_time: str, hours: list[float]) -> list[tuple[str, str]]:
	cursor = dt.datetime.fromisoformat(f"{date} {normalise_time(start_time)}")
	slots = []
	for value in hours:
		end = cursor + dt.timedelta(minutes=round(value * 60))
		slots.append((cursor.strftime(DATETIME_FORMAT), end.strftime(DATETIME_FORMAT)))
		cursor = end
	return slots


def activity_error(index: int, activity, activity_types: set[str], source: str = "cache") -> str:
	key = "".join(str(activity or "").lower().split())
	close = sorted(name for name in activity_types if "".join(name.lower().split()) == key)
	where = "run `catalogue list --type activity --match <word>` for the exact string"
	hint = f" — did you mean {', '.join(repr(name) for name in close)}?" if close else f" — {where}"
	return f"Entry {index}: {activity!r} is not a valid Activity Type{hint}"


def resolve_project(
	entry: dict, profile: dict, projects: dict, warnings: list[str], source: str = "cache"
) -> tuple[str, str]:
	"""(project id, project name). `source` is the catalogue the lookup used: 'cache' or 'none' (no warning)."""
	project = entry.get("project") or profile["project"]
	known = projects.get(project)
	if known:
		if known["status"] == "Completed":
			warnings.append(f"Project {project!r} is Completed")
		return project, known["short_code"]
	if source == "cache":
		warnings.append(
			f"Project {project!r} isn't in the cached open projects — it may be Completed or belong to another "
			"company; the site rejects a project that doesn't exist"
		)
	fallback = profile.get("project_name") if project == profile["project"] else None
	return project, entry.get("project_name") or fallback or project


def build_description(entry: dict) -> str:
	return render_description(entry.get("description") or entry.get("summary"), entry.get("links"))


def build_note(note, total: float) -> str:
	text = str(note or "").strip()
	marker = text.find("Total hours logged:")
	if marker != -1:
		text = text[:marker].rstrip()
	return f"{text} Total hours logged: {fmt_hours(total)}h.".strip()


def build_timesheet(
	spec: dict,
	profile: dict,
	activity_types: set[str] | None,
	projects: dict,
	*,
	currency: str | None = None,
	source: str = "cache",
) -> tuple[dict, list[str]]:
	"""The draft Timesheet and its warnings. `activity_types=None` skips Link validation (no catalogue for the site)."""
	date = parse_date(spec.get("date"))
	entries = spec.get("entries") or []
	if not entries:
		raise SuiteError("Spec has no entries")
	target = spec.get("target_total_hours")
	hours = resolve_hours(entries, target)
	slots = schedule(date, spec.get("start_time") or profile["start_time"], hours)

	warnings: list[str] = []
	if dt.date.fromisoformat(date).weekday() == 6:
		warnings.append(
			f"{date} is a Sunday — some sites (HRMS) refuse a timesheet while attendance is not marked Present; "
			"if the post fails with 'attendance is not marked Present', get attendance marked first"
		)
	time_logs = []
	for index, (entry, row_hours, (from_time, to_time)) in enumerate(zip(entries, hours, slots), 1):
		activity = entry.get("activity_type")
		if activity_types is not None and activity not in activity_types:
			raise SuiteError(activity_error(index, activity, activity_types, source))
		project, project_name = resolve_project(entry, profile, projects, warnings, source)
		if entry.get("hours") is None:
			warnings.append(
				f"Entry {index}: {fmt_hours(row_hours)}h split from the {fmt_hours(float(target))}h target"
			)
		elif entry.get("estimated") is True and abs(float(entry["hours"]) - row_hours) > 1e-6:
			warnings.append(
				f"Entry {index}: estimated {fmt_hours(float(entry['hours']))}h scaled to {fmt_hours(row_hours)}h "
				f"to fit the {fmt_hours(float(target))}h target"
			)
		row = {
			"doctype": "Timesheet Detail",
			"idx": index,
			"activity_type": activity,
			"from_time": from_time,
			"description": build_description(entry),
			"expected_hours": 0,
			"to_time": to_time,
			"hours": row_hours,
			"completed": 0,
			"project": project,
			"project_name": project_name,
			"is_billable": 0,
		}
		row.update(dict.fromkeys(ZERO_ROW_AMOUNTS, 0))
		time_logs.append(row)

	total = round(sum(hours), 2)
	doc = {
		"doctype": "Timesheet",
		"naming_series": "TS-.YYYY.-",
		"title": profile["employee_name"],
		"company": profile["company"],
		"currency": currency or "INR",
		"exchange_rate": 1,
		"status": "Draft",
		"docstatus": 0,
		"employee": profile["employee"],
		"employee_name": profile["employee_name"],
	}
	if profile.get("department"):
		doc["department"] = profile["department"]
	doc.update(
		start_date=date,
		end_date=slots[-1][1][:10],
		total_hours=total,
		note=build_note(spec.get("note"), total),
	)
	doc.update(dict.fromkeys(ZERO_TOTALS, 0))
	doc["time_logs"] = time_logs
	return doc, list(dict.fromkeys(warnings))


@dataclass
class BuildResult:
	"""Everything `build` writes or prints, computed without touching the disk."""

	doc: dict
	warnings: list[str]
	entries: list[dict]  # the entries after Jira resolution: what the timesheet rows AND the chat messages were built from
	rendered: dict[str, ts_chat.Rendered] = field(default_factory=dict)
	chat_error: str | None = None  # every target that could not fit, one per line; nothing was rendered then


def build_all(
	spec: dict,
	profile: dict,
	*,
	catalogue: ts_catalogue.Catalogue,
	digest: dict | None,
	targets: list[str] | None,
) -> BuildResult:
	"""Resolve Jira tickets, build the Timesheet against `catalogue`, then render the RESOLVED entries for each target.

	Pure: no files, no network, no environment. `targets` None or [] renders nothing. A render overflow is
	reported in `chat_error` (the timesheet is still returned) so the caller can write the JSON first.
	"""
	warnings: list[str] = []
	if catalogue.activity_types is None:
		warnings.append(ts_catalogue.UNVALIDATED_WARNING)
	entries, ticket_warnings = ts_jira.resolve_tickets(spec.get("entries") or [], digest, site=profile.get("jira_site"))
	warnings += ticket_warnings
	if not catalogue.currency:
		warnings.append("The site's currency is unknown — assuming INR; run `catalogue refresh` to read it from the site")
	doc, built = build_timesheet(
		{**spec, "entries": entries},
		profile,
		catalogue.activity_types,
		catalogue.projects,
		currency=catalogue.currency,
		source=catalogue.source,
	)
	warnings += built
	result = BuildResult(doc, warnings, entries)
	if targets:
		hours = [row["hours"] for row in doc["time_logs"]]
		try:
			result.rendered = ts_chat.render_all(targets, doc["start_date"], entries, hours, employee_name=profile["employee_name"])
		except SuiteError as exc:
			result.chat_error = str(exc)
		else:
			for rendered in result.rendered.values():
				warnings += rendered.warnings
	result.warnings = list(dict.fromkeys(warnings))
	return result


# GitHub


def repo_of(item: dict) -> str:
	return item["repository_url"].split("/repos/", 1)[1]


def _safe_detail(detail) -> str:
	"""Server text for an error line: printable, one line, capped, and never a credential."""
	text = "".join(char if char.isprintable() else " " for char in str(detail or ""))
	text = " ".join(text.split())
	if looks_like_secret(text):
		return "[redacted]"
	return text if len(text) <= 200 else text[:199].rstrip() + "…"


class GitHubClient:
	"""Minimal GitHub REST client for one day's commits, PRs, merges and reviews."""

	def __init__(self, token, timeout=30):
		token = clean_credential(token, "GITHUB_TOKEN")
		if not token:
			raise SuiteError("No GitHub token — set GITHUB_TOKEN")
		self.timeout = timeout
		self.opener = build_opener(GITHUB_API, True)
		self.headers = {
			"Authorization": f"Bearer {token}",
			"Accept": "application/vnd.github+json",
			"X-GitHub-Api-Version": "2022-11-28",
			"User-Agent": "timesheet-suite",
		}

	@classmethod
	def from_env(cls) -> GitHubClient:
		return cls(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))

	def get(self, path: str, params: dict | None = None):
		url = GITHUB_API + path + ("?" + urllib.parse.urlencode(params) if params else "")
		try:
			with self.opener.open(urllib.request.Request(url, headers=self.headers), timeout=self.timeout) as response:
				return json.loads(response.read().decode() or "null")
		except urllib.error.HTTPError as exc:
			try:
				detail = json.loads(exc.read().decode()).get("message", "")
			except (ValueError, AttributeError):
				detail = ""
			raise SuiteError(f"GitHub {path} failed ({exc.code}) {_safe_detail(detail)}".strip()) from None
		except urllib.error.URLError:
			raise SuiteError("Could not reach GitHub") from None
		except ValueError:
			raise SuiteError(f"GitHub {path} request could not be sent — check GITHUB_TOKEN for stray characters") from None

	def search(self, kind: str, query: str) -> tuple[list[dict], int]:
		items, total = [], 0
		for page in range(1, GITHUB_SEARCH_PAGES + 1):
			data = self.get(f"/search/{kind}", {"q": query, "per_page": 100, "page": page}) or {}
			batch = data.get("items") or []
			total = data.get("total_count", 0)
			items += batch
			if len(batch) < 100:
				break
		return items, total

	def pull(self, repo: str, number: int) -> dict:
		return self.get(f"/repos/{repo}/pulls/{number}") or {}

	def reviews(self, repo: str, number: int) -> list[dict]:
		return self.get(f"/repos/{repo}/pulls/{number}/reviews", {"per_page": 100}) or []

	def events(self, user: str) -> list[dict]:
		events = []
		for page in (1, 2, 3):
			batch = self.get(f"/users/{user}/events", {"per_page": 100, "page": page}) or []
			events += batch
			if len(batch) < 100:
				break
		return events

	def compare(self, repo: str, base: str, head: str) -> list[dict]:
		return (self.get(f"/repos/{repo}/compare/{base}...{head}") or {}).get("commits") or []

	def commit(self, repo: str, sha: str) -> dict:
		return self.get(f"/repos/{repo}/commits/{sha}") or {}


def github_digest(client, users, date, utc_offset=DEFAULT_UTC_OFFSET, orgs=None) -> dict:
	"""Collect one day's GitHub work for the given usernames. Failures become warnings, not crashes."""
	users = split_list(users)
	if not users:
		raise SuiteError("No GitHub usernames — pass --users or set github_users in the profile")
	window = day_window(date, utc_offset)
	span = f"{window[0].isoformat()}..{window[1].isoformat()}"
	logins = {user.lower() for user in users}
	commits, raised, merged, reviewed, errors = {}, {}, {}, {}, []

	def add_commit(repo, sha, message, authored_at, url, author):
		title, _, body = (message or "").strip().partition("\n")
		entry = commits.setdefault(
			(repo, title.strip()),
			{"repo": repo, "title": title.strip(), "details": clean_text(body, 400), "shas": [], "urls": [],
			 "authored_at": authored_at, "authors": []},
		)
		if sha[:7] not in entry["shas"]:
			entry["shas"].append(sha[:7])
			entry["urls"].append(url)
		if author and author not in entry["authors"]:
			entry["authors"].append(author)

	def attempt(label, action):
		try:
			action()
		except SuiteError as exc:
			errors.append(f"{label}: {exc}")

	for user in users:
		def searched_commits(user=user):
			items, total = client.search("commits", f"author:{user} author-date:{span}")
			for item in items:
				info = item["commit"]
				add_commit(item["repository"]["full_name"], item["sha"], info["message"], info["author"]["date"], item["html_url"], user)
			if total > len(items):
				errors.append(f"commits for {user}: {total} found, only the first {len(items)} used")

		def pushed_commits(user=user):
			# Commit search only covers default branches; push events show work on any branch.
			events = client.events(user)
			if events and parse_timestamp(events[-1]["created_at"]) > window[0]:
				errors.append(
					f"activity feed for {user} only reaches back to {events[-1]['created_at'][:10]} — "
					"commits pushed to non-default branches before then can't be seen"
				)
			for event in events:
				if event.get("type") != "PushEvent" or not in_window(event.get("created_at"), window):
					continue
				repo, payload = event["repo"]["name"], event.get("payload") or {}
				before, head = payload.get("before") or "", payload.get("head") or ""
				if not head:
					continue
				found = client.compare(repo, before, head) if before.strip("0") else [client.commit(repo, head)]
				for item in found:
					info = item.get("commit") or {}
					author = info.get("author") or {}
					login = ((item.get("author") or {}).get("login") or "").lower()
					name = (author.get("name") or "").lower()
					if (login in logins or name in logins) and in_window(author.get("date"), window):
						add_commit(repo, item["sha"], info.get("message"), author["date"], item.get("html_url"), login or name)

		def raised_prs(user=user):
			items, _ = client.search("issues", f"is:pr author:{user} created:{span}")
			for item in items:
				raised[(repo_of(item), item["number"])] = {
					"repo": repo_of(item), "number": item["number"], "title": item["title"], "url": item["html_url"],
					"state": item["state"], "merged": bool((item.get("pull_request") or {}).get("merged_at")),
					"author": user, "created_at": item["created_at"], "description": clean_text(item.get("body")),
				}

		def submitted_reviews(user=user):
			items, total = client.search("issues", f"is:pr reviewed-by:{user} updated:>={window[0].isoformat()}")
			for item in items:
				mine = [
					review for review in client.reviews(repo_of(item), item["number"])
					if ((review.get("user") or {}).get("login") or "").lower() == user.lower()
					and in_window(review.get("submitted_at"), window)
				]
				if mine:
					reviewed[(repo_of(item), item["number"])] = {
						"repo": repo_of(item), "number": item["number"], "title": item["title"], "url": item["html_url"],
						"author": (item.get("user") or {}).get("login"), "reviewer": user,
						"states": sorted({review["state"] for review in mine}), "submitted_at": mine[0]["submitted_at"],
					}
			if total > len(items):
				errors.append(f"reviews by {user}: {total} PRs updated since that day, only the first {len(items)} checked")

		attempt(f"commits for {user}", searched_commits)
		attempt(f"pushed commits for {user}", pushed_commits)
		attempt(f"PRs raised by {user}", raised_prs)
		attempt(f"reviews by {user}", submitted_reviews)

	org_list = split_list(orgs) or sorted({key[0].split("/")[0] for key in (*commits, *raised, *reviewed)})
	for org in org_list:
		def merged_prs(org=org):
			items, total = client.search("issues", f"is:pr is:merged org:{org} merged:{span}")
			for item in items:
				pr = client.pull(repo_of(item), item["number"])
				merged_by = (pr.get("merged_by") or {}).get("login") or ""
				if merged_by.lower() in logins:
					merged[(repo_of(item), item["number"])] = {
						"repo": repo_of(item), "number": item["number"], "title": pr.get("title") or item["title"],
						"url": pr.get("html_url") or item["html_url"], "author": (pr.get("user") or {}).get("login"),
						"merged_by": merged_by, "merged_at": pr.get("merged_at"), "additions": pr.get("additions"),
						"deletions": pr.get("deletions"), "description": clean_text(pr.get("body")),
						"branch": (pr.get("head") or {}).get("ref"),
					}
			if total > len(items):
				errors.append(f"PRs merged in {org}: {total} found, only the first {len(items)} checked")

		attempt(f"PRs merged in {org}", merged_prs)

	def ordered(values, field):
		return sorted(values, key=lambda item: parse_timestamp(item[field]) if item.get(field) else window[0])

	return {
		"date": parse_date(date), "utc_offset": parse_offset(utc_offset), "users": users, "orgs": org_list,
		"commits": ordered(commits.values(), "authored_at"),
		"prs_raised": ordered(raised.values(), "created_at"),
		"prs_merged": ordered(merged.values(), "merged_at"),
		"reviews": ordered(reviewed.values(), "submitted_at"),
		"errors": errors,
	}

# CLI


def _load_digest(path) -> dict:
	"""A Jira digest named explicitly with --jira-digest; same checks as `ts_jira.load_jira_digest`."""
	data = read_json(path)
	if not isinstance(data, dict) or data.get("version") != ts_jira.DIGEST_VERSION or not isinstance(data.get("tickets"), list):
		raise SuiteError(f"{path} is not a version-{ts_jira.DIGEST_VERSION} Jira digest")
	if normalise_site(data.get("site"), kind="jira") != data["site"]:
		raise SuiteError(f"{path} names a site that is not a Jira Cloud origin")
	return data


def _chat_targets(args, profile: dict) -> list[str] | None:
	"""`--chat-targets` (never saved) when given, else the profile's list; None means the user was never asked."""
	if split_list(args.chat_targets):
		return ts_chat.normalise_targets(args.chat_targets)
	return ts_chat.normalise_targets(profile.get("chat_targets"))


def cmd_build(args, env: Env) -> int:
	profile = env.load_profile()
	spec = read_json(args.spec)
	out_dir = out_dir_for(profile, args.out_dir)
	targets = _chat_targets(args, profile)
	digest = _load_digest(args.jira_digest) if args.jira_digest else ts_jira.load_jira_digest(out_dir, parse_date(spec.get("date")))
	catalogue = ts_catalogue.resolve_catalogue(profile["site"], profile)
	result = build_all(spec, profile, catalogue=catalogue, digest=digest, targets=targets)

	doc, hours = result.doc, [row["hours"] for row in result.doc["time_logs"]]
	json_path = out_dir / f"timesheet_{doc['start_date']}.json"
	write_private_json(json_path, doc)
	env.out(f"timesheet: {json_path}")
	env.out(
		f"total {fmt_hours(doc['total_hours'])}h across {len(hours)} rows · "
		f"catalogue: {ts_catalogue.source_label(catalogue, profile['site'])}"
	)
	for warning in result.warnings:
		env.out(f"warning: {warning}")
	if targets is None:
		env.out(CHAT_ASK)
		return 2
	if not targets:
		env.out("no chat targets saved — only the timesheet JSON was written")
		return 0
	if result.chat_error:
		print(f"error: {result.chat_error}", file=sys.stderr)
		return 1
	ts_chat.write_chat(out_dir, doc["start_date"], result.rendered)
	for target, rendered in result.rendered.items():
		names = ", ".join(ts_chat.chat_filename(target, doc["start_date"], suffix) for suffix in rendered.files)
		env.out(
			f"{target}: {names} · {rendered.size}/{rendered.limit} {rendered.unit} · "
			f"links embedded {rendered.embedded}/{rendered.links}"
		)
		if rendered.subject:
			env.out(f"  subject: {rendered.subject}")
	return 0


def cmd_github(args, env: Env) -> int:
	profile = env.read_profile() or {}
	digest = github_digest(
		GitHubClient.from_env(),
		args.users or profile.get("github_users"),
		args.date,
		args.utc_offset or profile.get("utc_offset") or DEFAULT_UTC_OFFSET,
		args.orgs or profile.get("github_orgs"),
	)
	out_path = Path(args.out).expanduser() if args.out else out_dir_for(profile) / f"github_{digest['date']}.json"
	write_private_json(out_path, digest)
	out = env.out
	out(f"github: {out_path}")
	out(
		f"commits {len(digest['commits'])} · PRs raised {len(digest['prs_raised'])} · "
		f"PRs merged {len(digest['prs_merged'])} · reviews {len(digest['reviews'])} · orgs {', '.join(digest['orgs']) or '-'}"
	)
	for item in digest["commits"]:
		out(f"  commit  {item['repo']} {', '.join(item['shas'])} {item['title']}")
	for item in digest["prs_raised"]:
		out(f"  raised  {item['repo']}#{item['number']} ({'merged' if item['merged'] else item['state']}) {item['title']}")
	for item in digest["prs_merged"]:
		out(f"  merged  {item['repo']}#{item['number']} by {item['merged_by']}, author {item['author']}: {item['title']}")
	for item in digest["reviews"]:
		out(f"  review  {item['repo']}#{item['number']} {'/'.join(item['states'])}, author {item['author']}: {item['title']}")
	for error in digest["errors"]:
		out(f"warning: {error}")
	return 0


def build_parser() -> tuple[argparse.ArgumentParser, dict]:
	parser = argparse.ArgumentParser(
		description="Timesheet Suite: profile, catalogue, build, GitHub, Jira, and site sync/update/amend/cancel/submit/pull.",
		allow_abbrev=False,
	)
	commands = parser.add_subparsers(dest="command", required=True)

	build = commands.add_parser("build", help="write the timesheet JSON and one message per chat app", allow_abbrev=False)
	build.add_argument("spec")
	build.add_argument("--out-dir")
	build.add_argument("--chat-targets", help="discord,slack,teams,gmail,whatsapp (CSV) or `none`; this run only, never saved")
	build.add_argument("--jira-digest", help="jira_<date>.json to resolve tickets from (default: next to the outputs)")

	github = commands.add_parser("github", help="optional: the day's commits, PRs, merges and reviews from GitHub", allow_abbrev=False)
	github.add_argument("--date", required=True)
	github.add_argument("--users", help="comma-separated GitHub usernames (default: profile github_users)")
	github.add_argument("--orgs", help="comma-separated orgs to look for merged PRs in (default: profile github_orgs)")
	github.add_argument("--utc-offset", help="the user's day, e.g. +05:30 (default: profile utc_offset)")
	github.add_argument("--out")

	handlers = {"build": cmd_build, "github": cmd_github}
	for module in (ts_profile, ts_catalogue, ts_chat, ts_jira, ts_lifecycle, ts_sessions, ts_post):
		handlers.update(module.add_parsers(commands))
	return parser, handlers


def main(argv: list[str] | None = None) -> int:
	parser, handlers = build_parser()
	args = parser.parse_args(argv)
	env = Env(
		load_profile=ts_profile.load_profile,
		read_profile=ts_profile.read_profile,
		client_factory=lambda site: ts_frappe.FrappeClient.from_env(site),
		out=print,
	)
	try:
		return handlers[args.command](args, env)
	except SuiteError as exc:
		print(f"error: {exc}", file=sys.stderr)
		return exc.exit_code
	except KeyboardInterrupt:
		print("interrupted", file=sys.stderr)
		return 130
	except OSError as exc:
		print(f"error: {exc.strerror or type(exc).__name__} — check the folder or file and its permissions", file=sys.stderr)
		return 1
	except Exception as exc:  # last resort: never a traceback, never the exception text (it may echo input)
		print(f"error: unexpected {type(exc).__name__} — re-run with the same command after checking inputs", file=sys.stderr)
		return 1


if __name__ == "__main__":
	sys.exit(main())
