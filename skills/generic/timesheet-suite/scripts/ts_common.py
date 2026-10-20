"""Shared helpers for the timesheet suite. Stdlib only; imports nothing else from the suite."""
from __future__ import annotations

import datetime as dt
import ipaddress
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

DEFAULT_OUT_DIR = "~/Downloads/timesheets"
DEFAULT_UTC_OFFSET = "+05:30"

SECRET_ENV_VARS = (
	"FRAPPE_API_KEY",
	"FRAPPE_API_SECRET",
	"FRAPPE_PASSWORD",
	"GITHUB_TOKEN",
	"GH_TOKEN",
	"JIRA_API_TOKEN",
)
SECRET_PREFIX = re.compile(r"(?<![A-Za-z0-9])(?:ghp_|gho_|ghs_|github_pat_|ATATT|xox[a-z]-)")
MIN_SECRET_LENGTH = 6


class SuiteError(Exception):
	"""Something the user or the model must fix; reported without a traceback."""

	exit_code = 1


@dataclass
class Env:
	"""What a command needs from the composition root; everything is resolved lazily."""

	load_profile: Callable[[], dict]
	read_profile: Callable[[], dict | None]
	client_factory: Callable[[str], object]
	out: Callable[[str], None] = print


# Text and time


def fmt_hours(hours: float) -> str:
	return f"{round(hours, 2):g}"


def split_list(value) -> list[str]:
	if isinstance(value, (list, tuple)):
		return [str(item).strip() for item in value if str(item).strip()]
	return [part.strip() for part in str(value or "").split(",") if part.strip()]


def clean_text(text, limit: int = 600) -> str:
	"""Plain-text gist of a PR description or commit body: no templates, checkboxes or bot trailers."""
	text = re.sub(r"<!--.*?-->", "", text or "", flags=re.S)
	kept = []
	for line in text.splitlines():
		line = re.sub(r"^\s*[-*]\s*\[[ xX]\]\s*", "- ", line).strip().lstrip("#").strip()
		if (
			not line
			or re.match(r"(co-authored-by|claude-session|signed-off-by):", line, re.I)
			or "Generated with [Claude Code]" in line
			or line.startswith("🤖")
			or re.fullmatch(r"https://claude\.ai/code/\S+", line)
		):
			continue
		kept.append(line)
	joined = re.sub(r"\*\*|`", "", " ".join(kept))
	return joined if len(joined) <= limit else joined[: limit - 1].rstrip() + "…"


def parse_date(value) -> str:
	try:
		return dt.date.fromisoformat(str(value)).isoformat()
	except ValueError:
		raise SuiteError(f"Spec date {value!r} is not YYYY-MM-DD") from None


def parse_offset(value) -> str:
	text = str(value).strip()
	if not re.fullmatch(r"[+-]\d{2}:\d{2}", text):
		raise SuiteError(f"UTC offset {value!r} must look like +05:30")
	return text


def parse_timestamp(value) -> dt.datetime:
	return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def day_window(date, utc_offset=DEFAULT_UTC_OFFSET) -> tuple[dt.datetime, dt.datetime]:
	start = dt.datetime.fromisoformat(f"{parse_date(date)}T00:00:00{parse_offset(utc_offset)}")
	return start, start + dt.timedelta(days=1, seconds=-1)


def in_window(value, window) -> bool:
	return bool(value) and window[0] <= parse_timestamp(value) <= window[1]


def normalise_time(value) -> str:
	text = " ".join(str(value).strip().upper().replace(".", ":").split())
	for pattern in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p", "%I %p", "%I%p"):
		try:
			return dt.datetime.strptime(text, pattern).strftime("%H:%M:%S")
		except ValueError:
			continue
	raise SuiteError(f"Unrecognised time {value!r} — use e.g. 09:30")


# Files


def read_json(path) -> dict:
	try:
		data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
	except FileNotFoundError:
		raise SuiteError(f"No such file: {path}") from None
	except json.JSONDecodeError as exc:
		raise SuiteError(f"{path} is not valid JSON: {exc}") from None
	except RecursionError:
		raise SuiteError(f"{path} is not valid JSON: nested too deeply") from None
	except UnicodeDecodeError:
		raise SuiteError(f"{path} is not valid JSON: not UTF-8 text") from None
	except OSError as exc:
		raise SuiteError(f"Cannot read {path}: {exc.strerror or exc.__class__.__name__}") from None
	if not isinstance(data, dict):
		raise SuiteError(f"{path} must be a JSON object")
	return data


def config_dir() -> Path:
	base = os.environ.get("TIMESHEET_SUITE_HOME")
	return Path(base).expanduser() if base else Path.home() / ".config" / "timesheet-suite"


def out_dir_for(profile: dict | None, override: str | None = None) -> Path:
	return Path(override or (profile or {}).get("out_dir") or DEFAULT_OUT_DIR).expanduser()


def _make_private_dirs(folder: Path) -> None:
	"""Create `folder` and every missing parent as 0700; a directory that already exists is left alone."""
	missing = []
	probe = folder
	while not probe.exists():
		missing.append(probe)
		if probe.parent == probe:
			break
		probe = probe.parent
	for created in reversed(missing):
		try:
			created.mkdir(mode=0o700)
		except FileExistsError:
			continue
		created.chmod(0o700)  # mkdir's mode is masked by the umask


def write_private_text(path, text: str) -> None:
	"""Write `text` to `path` as 0600; the old file survives any failure.

	Directories this call creates are 0700. A directory that already exists keeps its mode, except the
	suite's own config_dir(), which is forced to 0700 whenever `path` lives inside it.
	"""
	path = Path(path)
	temp = None
	try:
		_make_private_dirs(path.parent)
		home = config_dir()
		if home == path.parent or home in path.parent.parents:
			home.chmod(0o700)
		handle, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
		with os.fdopen(handle, "wb") as stream:
			stream.write(text.encode("utf-8"))
			stream.flush()
			os.fsync(stream.fileno())
		os.chmod(temp, 0o600)
		os.replace(temp, path)
	except OSError as exc:
		if temp:
			try:
				os.unlink(temp)
			except FileNotFoundError:
				pass
		raise SuiteError(f"Could not write {path}: {exc.strerror or exc}") from None
	except BaseException:
		if temp:
			try:
				os.unlink(temp)
			except FileNotFoundError:
				pass
		raise


def write_private_json(path, data) -> None:
	write_private_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


# Sites


def _site_error(kind: str) -> SuiteError:
	if kind == "jira":
		return SuiteError("That is not a Jira Cloud site — give the full address, e.g. acme.atlassian.net")
	return SuiteError("That is not a Frappe site — give a site name or URL, e.g. erp.example.com")


def _valid_host(host: str) -> str | None:
	"""Return the canonical (lowercase, IDNA) host, or None when it is not a hostname/IP literal."""
	try:
		return ipaddress.ip_address(host).compressed
	except ValueError:
		pass
	try:
		host = host.encode("idna").decode("ascii")
	except UnicodeError:
		return None
	host = host.lower()
	if len(host) > 253:
		return None
	labels = host.split(".")
	if all(re.fullmatch(r"(?!-)[a-z0-9-]{1,63}(?<!-)", label) for label in labels):
		return host
	return None


def is_loopback_host(host: str) -> bool:
	if host == "localhost" or host.endswith(".localhost"):
		return True
	try:
		return ipaddress.ip_address(host).is_loopback
	except ValueError:
		return False


def normalise_site(value, kind: str = "frappe") -> str:
	"""Reduce what a person typed or pasted to an origin; refuse anything credentials must not go to.

	kind="frappe": https enforced (plain http only for loopback); a bare bench name such as `bench`
	maps to `http://bench.localhost:8000`.
	kind="jira": only `https://<label>.atlassian.net`.
	Rejected text is never echoed: it may be a pasted credential.
	"""
	if kind not in ("frappe", "jira"):
		raise ValueError(f"unknown site kind {kind!r}")
	if not isinstance(value, str):
		raise _site_error(kind)
	text = value.strip()
	if not text or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in text):
		raise _site_error(kind)
	explicit_scheme = "://" in text
	try:
		parts = urllib.parse.urlsplit(text if explicit_scheme else "https://" + text)
		port = parts.port
		host = parts.hostname
	except ValueError:
		raise _site_error(kind) from None
	if parts.scheme not in ("http", "https") or not host:
		raise _site_error(kind)
	if "@" in parts.netloc:
		raise SuiteError("Site must not contain a username/password")
	if port is not None and not 1 <= port <= 65535:
		raise _site_error(kind)
	host = _valid_host(host[:-1] if host.endswith(".") else host)
	if host is None:
		raise _site_error(kind)

	scheme = parts.scheme
	if kind == "jira":
		if scheme != "https" or port not in (None, 443) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.atlassian\.net", host):
			raise _site_error(kind)
		return f"https://{host}"

	if not explicit_scheme and port is None and "." not in host and ":" not in host and host != "localhost":
		host, scheme, port = f"{host}.localhost", "http", 8000  # a bare bench name
	elif not explicit_scheme and is_loopback_host(host):
		scheme = "http"
	if scheme == "http" and not is_loopback_host(host):
		raise SuiteError(
			f"Refusing plain http for remote site {host!r} — credentials would travel unencrypted; use https://"
		)
	if port == {"https": 443, "http": 80}[scheme]:
		port = None
	shown = f"[{host}]" if ":" in host else host
	return f"{scheme}://{shown}" + (f":{port}" if port else "")


def site_host(site: str) -> str:
	"""`host[:port]` of a normalised site."""
	return urllib.parse.urlsplit(site).netloc


def site_slug(site: str) -> str:
	"""A path-safe directory name for a site: `[a-z0-9_][a-z0-9._-]*`."""
	host = site_host(site).lower()
	if not host:
		raise SuiteError("Cannot name a cache folder for an empty site")
	slug = re.sub(r"[^a-z0-9._-]", "_", host)
	return "_" + slug[1:] if slug[0] == "." else slug


def origin_of(url: str) -> tuple[str, str, int]:
	"""(scheme, lowercase host, port) with the scheme's default port filled in."""
	try:
		parts = urllib.parse.urlsplit(url)
		port = parts.port
	except ValueError:
		raise SuiteError("Not a valid URL origin") from None
	if parts.scheme not in ("http", "https") or not parts.hostname:
		raise SuiteError("Not a valid URL origin")
	return parts.scheme, parts.hostname.lower(), port or {"https": 443, "http": 80}[parts.scheme]


def looks_like_secret(value) -> bool:
	"""True when `value` contains a current environment secret or a well-known token prefix."""
	if not isinstance(value, str) or not value:
		return False
	for name in SECRET_ENV_VARS:
		secret = os.environ.get(name) or ""
		if len(secret) >= MIN_SECRET_LENGTH and secret in value:
			return True
	return bool(SECRET_PREFIX.search(value))


def clean_credential(value, label: str) -> str | None:
	"""A credential from the environment, stripped; None when empty. Never echoes the value."""
	text = (value or "").strip()
	if not text:
		return None
	if any(ord(char) < 0x20 or ord(char) == 0x7F for char in text):
		raise SuiteError(f"{label} contains control characters")
	return text


def validate_email(value) -> str:
	text = value.strip() if isinstance(value, str) else ""
	if len(text) > 254 or not re.fullmatch(r"[^@\s:]+@[^@\s:]+\.[^@\s:]+", text):
		raise SuiteError("That is not a valid email address — it must look like name@example.com (never add a token)")
	return text


# HTTP


class _OriginRedirect(urllib.request.HTTPRedirectHandler):
	"""Follow a redirect only when it stays on one origin, is a GET, and following is allowed."""

	def __init__(self, origin: tuple[str, str, int], follow_same_origin_get: bool):
		self.origin = origin
		self.follow = follow_same_origin_get

	def redirect_request(self, req, fp, code, msg, headers, newurl):
		target = origin_of(urllib.parse.urljoin(req.full_url, newurl))
		if target != self.origin:
			fp.close()
			raise SuiteError(
				f"Server redirected to a different origin ({target[1]}) — refusing to send credentials; fix the site"
			)
		if not self.follow or req.get_method() != "GET":
			fp.close()
			raise SuiteError(f"Server answered {code} with a redirect — refusing to follow it")
		return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_opener(origin, follow_same_origin_get: bool, extra_handlers=()) -> urllib.request.OpenerDirector:
	"""An opener that never lets a redirect carry credentials off `origin` (URL or origin tuple).

	Pass `urllib.request.ProxyHandler({})` in `extra_handlers` to bypass proxy environment variables.
	"""
	pinned = origin if isinstance(origin, tuple) else origin_of(origin)
	return urllib.request.build_opener(_OriginRedirect(pinned, follow_same_origin_get), *extra_handlers)


# Timesheet row descriptions


_REF_LINE = re.compile(r"Ref: (https?://\S+)")


def render_description(text, links) -> str:
	"""`text`, a blank line, then one `Ref: <url>` line per http(s) link (deduplicated, in order)."""
	body = str(text or "").strip()
	urls = []
	for link in links or []:
		url = str((link or {}).get("url") or "").strip()
		if re.fullmatch(r"https?://\S+", url) and url not in urls:
			urls.append(url)
	refs = "\n".join(f"Ref: {url}" for url in urls)
	return "\n\n".join(part for part in (body, refs) if part)


def split_description(desc) -> tuple[str, list[dict]]:
	"""Inverse of render_description: trailing `Ref: <http(s) url>` lines become links, the rest stays text."""
	lines = str(desc or "").split("\n")
	links: list[dict] = []
	while lines:
		match = _REF_LINE.fullmatch(lines[-1].rstrip())
		if not match:
			break
		links.insert(0, {"url": match.group(1)})
		lines.pop()
	return "\n".join(lines).rstrip(), links
