"""Activity Type / Project catalogues: the per-site cache read from the site itself. Stdlib only.

Imports ts_common only. `fetch_catalogue` takes any client with `list_docs` (the composition root hands
one over through `Env.client_factory`), so this module never touches the network itself.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ts_common import Env, SuiteError, config_dir, normalise_site, site_host, site_slug, write_private_text

SCHEMA = 1
ACTIVITY_HEADER = ["Activity Type", "Default Costing Rate", "Default Billing Rate", "Disabled"]
PROJECT_HEADER = ["Project ID (docname / Link value)", "Short Code", "Status", "Company"]
UNVALIDATED_WARNING = (
	"Activity Types and Projects are not validated for this site — it will reject unknown ones on sync; "
	"run `catalogue refresh` (needs API credentials for the site) to validate offline."
)

__all__ = [
	"UNVALIDATED_WARNING",
	"Catalogue",
	"load_activity_types",
	"load_projects",
	"catalogue_dir",
	"fetch_catalogue",
	"write_catalogue",
	"read_catalogue",
	"resolve_catalogue",
	"source_label",
	"add_parsers",
]


def load_activity_types(path: Path) -> set[str]:
	with path.open(newline="", encoding="utf-8") as handle:
		return {
			row["Activity Type"]
			for row in csv.DictReader(handle)
			if str(row.get("Disabled", "0")).strip() in ("", "0")
		}


def load_projects(path: Path) -> dict[str, dict]:
	with path.open(newline="", encoding="utf-8") as handle:
		rows = list(csv.reader(handle))[1:]
	return {
		row[0]: {"short_code": row[1], "status": row[2], "company": row[3]} for row in rows if len(row) >= 4
	}


@dataclass
class Catalogue:
	"""What a build validates against. `source` is 'cache' or 'none' (activity_types None = skip validation)."""

	activity_types: set[str] | None = None
	projects: dict[str, dict] = field(default_factory=dict)
	fetched_at: str | None = None
	counts: dict[str, int] = field(default_factory=dict)
	currency: str | None = None
	source: str = "none"


# Cache


def catalogue_dir(site: str) -> Path:
	return config_dir() / "catalogues" / site_slug(site)


def _unreadable(site: str, folder: Path) -> SuiteError:
	return SuiteError(f"catalogue cache for {site} is unreadable ({folder}) — run catalogue refresh")


def _list(client, doctype: str, filters: list, fields: list) -> list[dict]:
	return [row for row in client.list_docs(doctype, filters, fields, order_by="name asc") if str(row.get("name") or "")]


def fetch_catalogue(client, company: str | None) -> dict:
	"""Read-only queries: enabled Activity Types, Open Projects, and the company's default currency (non-fatal).

	`company` is never read from Project rows: users with only `select` permission on Project get rows
	without it. Rows are whatever the login may see.
	"""
	activity = [row["name"] for row in _list(client, "Activity Type", [["disabled", "=", 0]], ["name", "disabled"])]
	if not activity:
		raise SuiteError("Activity Type list came back empty from the site — cache left unchanged")
	projects = [
		{"name": row["name"], "project_name": row.get("project_name") or "", "status": row.get("status") or "Open"}
		for row in _list(client, "Project", [["status", "=", "Open"]], ["name", "project_name", "status"])
	]
	currency = None
	if company:
		try:
			rows = client.list_docs("Company", [["name", "=", company]], ["default_currency"])
			currency = (rows[0].get("default_currency") or None) if rows else None
		except SuiteError:
			currency = None
	return {"activity_types": activity, "projects": projects, "currency": currency}


def _csv_text(header: list[str], rows: list[list]) -> str:
	buffer = io.StringIO(newline="")
	writer = csv.writer(buffer, lineterminator="\n")
	writer.writerow(header)
	writer.writerows(rows)
	return buffer.getvalue()


def write_catalogue(site: str, data: dict, now: dt.datetime) -> Path:
	"""Write the two CSVs, then the meta LAST; `read_catalogue` rejects a cache whose meta counts do not match."""
	folder = catalogue_dir(site)
	write_private_text(
		folder / "activity_types.csv",
		_csv_text(ACTIVITY_HEADER, [[name, "0.0", "0.0", "0"] for name in data["activity_types"]]),
	)
	write_private_text(
		folder / "projects.csv",
		_csv_text(PROJECT_HEADER, [[row["name"], row["project_name"], row["status"], ""] for row in data["projects"]]),
	)
	meta = {
		"schema": SCHEMA,
		"site": site,
		"fetched_at": now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
		"counts": {"activity_types": len(data["activity_types"]), "projects": len(data["projects"])},
		"currency": data.get("currency"),
	}
	write_private_text(folder / "catalogue.json", json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
	return folder


def read_catalogue(site: str) -> Catalogue | None:
	"""None when this site has no cache (or the meta names another site); SuiteError when the cache is damaged."""
	folder = catalogue_dir(site)
	meta_path = folder / "catalogue.json"
	if not meta_path.exists():
		return None
	try:
		meta = json.loads(meta_path.read_text(encoding="utf-8"))
		counts, fetched_at, currency = meta["counts"], meta["fetched_at"], meta.get("currency")
		valid = (
			meta["schema"] == SCHEMA
			and isinstance(meta["site"], str)
			and isinstance(fetched_at, str)
			and (currency is None or isinstance(currency, str))
			and isinstance(counts, dict)
			and all(type(counts.get(key)) is int for key in ("activity_types", "projects"))
		)
		if not valid:
			raise ValueError("bad meta")
		if meta["site"] != site:
			return None
		activity_types = load_activity_types(folder / "activity_types.csv")
		projects = load_projects(folder / "projects.csv")
	except (OSError, ValueError, KeyError, TypeError, AttributeError, csv.Error):
		raise _unreadable(site, folder) from None
	if (len(activity_types), len(projects)) != (counts["activity_types"], counts["projects"]):
		raise _unreadable(site, folder)
	return Catalogue(
		activity_types=activity_types,
		projects=projects,
		fetched_at=fetched_at,
		counts={"activity_types": len(activity_types), "projects": len(projects)},
		currency=currency,
		source="cache",
	)


def resolve_catalogue(site: str, profile: dict | None = None) -> Catalogue:
	"""The catalogue a build validates against: this site's cache, else nothing.

	With no cache the result has `activity_types=None`: skip Link validation and warn once with
	UNVALIDATED_WARNING. A damaged cache raises (fail closed). `profile` is accepted for the build-flow contract.
	"""
	cached = read_catalogue(site)
	return cached if cached is not None else Catalogue()


def source_label(catalogue: Catalogue, site: str) -> str:
	if catalogue.source == "cache":
		return f"cache {site_host(site)} (refreshed {(catalogue.fetched_at or '')[:10]})"
	return "none"


# CLI


def _setup_error(message: str) -> SuiteError:
	error = SuiteError(message)
	error.exit_code = 2
	return error


def _site_for(args: argparse.Namespace, profile: dict, *, allow_flag: bool) -> str:
	"""The profile's site; `--site` only on first run or when it equals the stored one (credentials never follow a flag)."""
	stored = normalise_site(profile["site"]) if profile.get("site") else None
	given = normalise_site(args.site) if allow_flag and getattr(args, "site", None) else None
	if given and stored and given != stored:
		raise _setup_error(
			f"profile site is {stored}, not {given} — to use another site run "
			f"`profile set --site {given} --confirm-site-change {given}` first"
		)
	site = given or stored
	if not site:
		raise _setup_error("No site yet — run `profile set --site <site>` first" + (" or pass --site" if allow_flag else ""))
	return site


def _diff(before: set[str] | None, after: set[str]) -> str:
	before = before or set()
	return f"+{len(after - before)} -{len(before - after)}"


def cmd_refresh(args: argparse.Namespace, env: Env) -> int:
	profile = env.read_profile() or {}
	site = _site_for(args, profile, allow_flag=True)
	try:
		previous = read_catalogue(site)
	except SuiteError:
		previous = None  # a damaged cache is exactly what refresh repairs
	env.out(f"site: {site}")
	data = fetch_catalogue(env.client_factory(site), profile.get("company"))
	folder = write_catalogue(site, data, dt.datetime.now(dt.timezone.utc))
	activity = set(data["activity_types"])
	projects = {row["name"] for row in data["projects"]}
	env.out(f"activity types: {len(activity)} ({_diff(previous and previous.activity_types, activity)})")
	env.out(f"projects: {len(projects)} ({_diff(previous and set(previous.projects), projects)})")
	if data["currency"]:
		env.out(f"currency: {data['currency']}")
	else:
		env.out("currency: unknown (no company set or the Company lookup failed) — builds will assume INR")
	env.out(f"cached in {folder} (the site itself was only read)")
	return 0


def cmd_list(args: argparse.Namespace, env: Env) -> int:
	profile = env.read_profile() or {}
	site = _site_for(args, profile, allow_flag=False)
	catalogue = resolve_catalogue(site, profile)
	needle = (args.match or "").lower()
	if catalogue.source == "none":
		env.out(f"source: none — nothing is validated for {site_host(site)}; run `catalogue refresh`")
		return 0
	counts = catalogue.counts
	env.out(
		f"source: {source_label(catalogue, site)} — {counts['activity_types']} activity types, {counts['projects']} projects"
	)
	if args.type in (None, "activity"):
		hits = sorted(name for name in catalogue.activity_types or () if needle in name.lower())
		if args.type is None:
			env.out("activity types:")
		env.out("\n".join(f"  {name}" for name in hits) if hits else "  (no match)")
	if args.type in (None, "project"):
		hits = [
			f"  {name} | {row['short_code']} | {row['status']}"
			for name, row in sorted(catalogue.projects.items())
			if needle in f"{name} {row['short_code']}".lower()
		]
		if args.type is None:
			env.out("projects:")
		env.out("\n".join(hits) if hits else "  (no match)")
	return 0


def add_parsers(commands) -> dict[str, Callable[[argparse.Namespace, Env], int]]:
	catalogue = commands.add_parser(
		"catalogue", help="refresh or search the Activity Type / Project lists of the profile's site", allow_abbrev=False
	)
	sub = catalogue.add_subparsers(dest="catalogue_command", required=True)
	refresh = sub.add_parser("refresh", help="read the lists from the site into the local cache", allow_abbrev=False)
	refresh.add_argument("--site", help="first run only, or the stored site spelled differently")
	listing = sub.add_parser("list", help="search the catalogue a build would validate against", allow_abbrev=False)
	listing.add_argument("--type", choices=("activity", "project"), help="only activity types or only projects")
	listing.add_argument("--match", help="case-insensitive substring")

	def handle(args: argparse.Namespace, env: Env) -> int:
		return {"refresh": cmd_refresh, "list": cmd_list}[args.catalogue_command](args, env)

	return {"catalogue": handle}
