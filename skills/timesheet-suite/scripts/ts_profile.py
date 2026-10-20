"""Saved profile (storage, validation, `profile` commands). Stdlib only; imports ts_common and ts_chat only.

The profile lives in `config_dir()/profile.json` (0600 in a 0700 folder). Credentials are never stored:
every value is checked with `looks_like_secret`, and rejected text is never echoed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from ts_chat import normalise_targets, resolve_target_change
from ts_common import (
	Env,
	SuiteError,
	config_dir,
	looks_like_secret,
	normalise_site,
	normalise_time,
	parse_offset,
	validate_email,
	write_private_json,
)

PROFILE_VERSION = 2
SETTABLE_FIELDS = (
	"site",
	"employee",
	"employee_name",
	"company",
	"department",
	"project",
	"project_name",
	"start_time",
	"utc_offset",
	"out_dir",
	"chat_targets",
	"github_users",
	"github_orgs",
	"jira_site",
	"jira_email",
	"session_roots",
)
PROFILE_FIELDS = SETTABLE_FIELDS + ("profile_version",)
REQUIRED_PROFILE_FIELDS = ("site", "employee", "company", "project", "start_time", "employee_name")
MAX_VALUE = 140
MAX_PATH_VALUE = 500


class SetupError(SuiteError):
	"""Something has to be asked or confirmed before work can go on (exit code 2)."""

	exit_code = 2


def profile_path() -> Path:
	return config_dir() / "profile.json"


def _check_text(field: str, value: str) -> str:
	if looks_like_secret(value):
		raise SuiteError(f"{field} looks like a credential — credentials are never stored (use the environment variable)")
	if any(ord(char) < 32 or ord(char) == 127 for char in value):
		raise SuiteError(f"{field} must be a single line of plain text")
	if len(value) > (MAX_PATH_VALUE if field == "out_dir" else MAX_VALUE):
		raise SuiteError(f"{field} is too long")
	return value


def _clean_value(field: str, value):
	"""Validate and normalise one incoming value; None means 'nothing to set'."""
	if value is None:
		return None
	if field == "chat_targets":
		if isinstance(value, str):
			value = value.strip()
			if not value:
				return None
			_check_text(field, value)
		else:
			for name in value:
				_check_text(field, str(name))
		return normalise_targets(value)
	if isinstance(value, (list, tuple)) and field in ("github_users", "github_orgs"):
		value = ",".join(str(item).strip() for item in value if str(item).strip())
	if not isinstance(value, str):
		raise SuiteError(f"{field} must be text")
	value = value.strip()
	if not value:
		return None
	_check_text(field, value)
	if field == "site":
		return normalise_site(value, kind="frappe")
	if field == "jira_site":
		return normalise_site(value, kind="jira")
	if field == "jira_email":
		return validate_email(value)
	if field == "start_time":
		return normalise_time(value)
	if field == "utc_offset":
		return parse_offset(value)
	return value


def upgrade_profile(raw: dict) -> dict:
	"""v1 -> v2 in memory; never invents `site` or `chat_targets`. A stored site that no longer validates is dropped."""
	if not isinstance(raw, dict):
		raise SuiteError(f"{profile_path()} is corrupt (it must hold a JSON object) — fix or move it; it is not overwritten")
	version = raw.get("profile_version", 1)
	if not isinstance(version, int) or isinstance(version, bool) or version < 1:
		raise SuiteError(f"{profile_path()} is corrupt (invalid profile_version) — fix or move it; it is not overwritten")
	if version > PROFILE_VERSION:
		raise SuiteError(f"profile.json was written by a newer timesheet-suite (v{version}) — update the skill")
	profile = {key: value for key, value in raw.items() if key != "profile_version"}
	if "site" in profile:
		try:
			profile["site"] = normalise_site(profile["site"], kind="frappe")
		except SuiteError:
			del profile["site"]
	return {"profile_version": PROFILE_VERSION, **profile}


def read_profile() -> dict | None:
	"""The upgraded profile, None when there is none; a corrupt or too-new file is a SuiteError."""
	path = profile_path()
	try:
		text = path.read_text(encoding="utf-8")
		raw = json.loads(text)
	except FileNotFoundError:
		return None
	except json.JSONDecodeError as exc:
		raise SuiteError(f"{path} is corrupt (not valid JSON: {exc.msg}) — fix or move it; it is not overwritten") from None
	except (UnicodeDecodeError, RecursionError):
		raise SuiteError(f"{path} is corrupt (not a UTF-8 JSON text) — fix or move it; it is not overwritten") from None
	except OSError as exc:
		raise SuiteError(f"{path} is unreadable ({exc.strerror or type(exc).__name__}) — fix or move it; it is not overwritten") from None
	return upgrade_profile(raw)


def missing_fields(profile: dict | None) -> list[str]:
	"""Required fields that are empty, then `chat_targets` when it was never asked (None; `[]` is an answer)."""
	profile = profile or {}
	missing = [field for field in REQUIRED_PROFILE_FIELDS if not profile.get(field)]
	if profile.get("chat_targets") is None:
		missing.append("chat_targets")
	return missing


def load_profile() -> dict:
	"""The profile with every required field present; `chat_targets` may still be None (see `missing_fields`)."""
	profile = read_profile()
	if profile is None:
		raise SetupError(f"No profile yet at {profile_path()} — ask for it and run `profile set`.")
	missing = [field for field in REQUIRED_PROFILE_FIELDS if not profile.get(field)]
	if missing:
		raise SetupError(f"Profile is missing {', '.join(missing)} — run `profile set` with those flags.")
	return profile


def save_profile(values: dict, unset=(), confirm_site_change: str | None = None) -> Path:
	"""Merge `values` onto the stored profile and write it atomically.

	Blank values are ignored (only `unset` erases). A stored `site` can be replaced only with
	`confirm_site_change` equal to the new normalised origin, so credentials cannot be re-aimed by accident.
	Nothing is written when anything is invalid or the stored file is corrupt.
	"""
	unknown = sorted(set(values) - set(SETTABLE_FIELDS))
	if unknown:
		raise SuiteError(f"Not a profile field: {', '.join(unknown)} (credentials are never stored)")
	bad_unset = sorted(set(unset) - set(SETTABLE_FIELDS))
	if bad_unset:
		raise SuiteError(f"Cannot unset {', '.join(bad_unset)} — not an optional profile field")
	if "site" in unset:
		raise SuiteError("site is required — replace it with `profile set --site …` instead of unsetting it")
	profile = read_profile() or {"profile_version": PROFILE_VERSION}
	for field, value in values.items():
		cleaned = _clean_value(field, value)
		if cleaned is not None:
			profile[field] = cleaned
	old_site = (read_profile() or {}).get("site")
	new_site = profile.get("site")
	if old_site and new_site != old_site and confirm_site_change != new_site:
		raise SetupError(
			f"Changing the site from {old_site} to {new_site} re-aims the saved credentials. "
			f"Confirm with the user, then re-run with --confirm-site-change {new_site}"
		)
	for field in unset:
		profile.pop(field, None)
	profile["profile_version"] = PROFILE_VERSION
	path = profile_path()
	write_private_json(path, {"profile_version": PROFILE_VERSION, **{k: v for k, v in profile.items() if k != "profile_version"}})
	return path


# Commands


def _blank_to_none(value):
	return value if isinstance(value, str) and value.strip() else None


def _print_missing(env: Env, profile: dict | None) -> list[str]:
	missing = missing_fields(profile)
	for field in missing:
		env.out(f"missing: {field}")
	return missing


def cmd_show(args, env: Env) -> int:
	profile = env.read_profile()
	if profile is None:
		env.out(f"No profile yet ({profile_path()}). Ask for the fields listed below, then run `profile set`.")
	else:
		env.out(json.dumps(profile, indent=2, ensure_ascii=False))
	return 2 if _print_missing(env, profile) else 0


def cmd_set(args, env: Env) -> int:
	stored = env.read_profile() or {}
	values = {field: _blank_to_none(getattr(args, field)) for field in SETTABLE_FIELDS}
	current = stored.get("chat_targets")
	chat_set, chat_add, chat_remove = (
		_blank_to_none(args.chat_targets),
		_blank_to_none(args.add_chat_targets),
		_blank_to_none(args.remove_chat_targets),
	)
	for field, flag in (("chat_targets", chat_set), ("add", chat_add), ("remove", chat_remove)):
		if flag is not None and looks_like_secret(flag):
			raise SuiteError("chat targets look like a credential — credentials are never stored (use the environment variable)")
	targets, notes = resolve_target_change(current, chat_set, chat_add, chat_remove)
	values["chat_targets"] = None if current is None and chat_set is None and chat_add is None else targets
	confirm = _blank_to_none(args.confirm_site_change)
	path = save_profile(values, confirm_site_change=confirm.strip() if confirm else None)
	saved = read_profile() or {}
	env.out(f"saved: {path}")
	env.out(f"site: {saved.get('site', '(not set)')}")
	if stored.get("site") and saved.get("site") != stored["site"]:
		env.out(
			f"warning: site changed from {stored['site']} to {saved['site']} — employee, company and project were "
			"set for the old site; re-check them (profile resolve)"
		)
	for note in notes:
		env.out(f"note: {note}")
	env.out(json.dumps(saved, indent=2, ensure_ascii=False))
	_print_missing(env, saved)
	return 0


def cmd_unset(args, env: Env) -> int:
	path = save_profile({}, unset=tuple(args.fields))
	saved = read_profile() or {}
	env.out(f"saved: {path}")
	env.out(json.dumps(saved, indent=2, ensure_ascii=False))
	_print_missing(env, saved)
	return 0


def _resolve_site(args, env: Env) -> str | None:
	stored = (env.read_profile() or {}).get("site")
	given = normalise_site(args.site, kind="frappe") if _blank_to_none(args.site) else None
	if stored and given and given != stored:
		raise SetupError(
			f"The profile site is {stored}, not {given}. Credentials only go to the saved site; to change it run "
			f"`profile set --site {given} --confirm-site-change {given}` first."
		)
	return stored or given


def cmd_resolve(args, env: Env) -> int:
	"""Read-only: list the Employee records of the logged-in user so the user can confirm one; writes nothing."""
	site = _resolve_site(args, env)
	if site is None:
		env.out("No site known yet — ask for the Frappe site, or pass --site.")
		env.out("missing: site")
		return 2
	client = env.client_factory(site)
	user = client.logged_user()
	try:
		rows = client.employees_for_user(user)
	except SuiteError as exc:
		if getattr(exc, "status", None) == 403:
			raise SuiteError(
				"The site refused the Employee lookup (403): this login can't read Employee; type the details instead"
			) from None
		raise
	if not rows:
		raise SuiteError(f"No Employee has user_id={user!r} on {site} — type the details instead")
	fields = ("name", "employee_name", "company", "department", "status")
	employees = [{field: row.get(field) for field in fields} for row in rows]
	env.out(json.dumps({"site": site, "user": user, "employees": employees}, indent=2, ensure_ascii=False))
	for row in employees:
		if row["status"] != "Active":
			env.out(f"warning: {row['name']} is {row['status'] or 'of unknown status'}, not Active — it cannot be used for new timesheets")
	if len(employees) > 1:
		env.out("note: several Employee records — confirm with the user which one to save; none was chosen")
	return 0


def add_parsers(commands) -> dict[str, Callable[[argparse.Namespace, Env], int]]:
	profile = commands.add_parser("profile", help="show, set, unset or resolve the saved profile", allow_abbrev=False)
	sub = profile.add_subparsers(dest="profile_command", required=True)
	sub.add_parser("show", help="print the profile and one `missing:` line per field still to ask", allow_abbrev=False)

	setter = sub.add_parser("set", help="save profile fields (blank values are ignored)", allow_abbrev=False)
	for field in SETTABLE_FIELDS:
		if field != "chat_targets":
			setter.add_argument("--" + field.replace("_", "-"), dest=field)
	setter.add_argument("--chat-targets", help="discord,slack,teams,gmail,whatsapp (CSV); `none` = no chat message")
	setter.add_argument("--add-chat-targets", help="CSV of targets to add")
	setter.add_argument("--remove-chat-targets", help="CSV of targets to remove")
	setter.add_argument("--confirm-site-change", help="the new normalised site origin; needed to replace a stored site")

	unsetter = sub.add_parser("unset", help="erase optional fields", allow_abbrev=False)
	unsetter.add_argument("fields", nargs="+", metavar="FIELD")

	resolver = sub.add_parser(
		"resolve", help="list your Employee records from the site (read-only)", allow_abbrev=False
	)
	resolver.add_argument("--site", help="only when no site is saved yet, or equal to the saved one")

	table = {"show": cmd_show, "set": cmd_set, "unset": cmd_unset, "resolve": cmd_resolve}

	def handle(args: argparse.Namespace, env: Env) -> int:
		return table[args.profile_command](args, env)

	return {"profile": handle}
