# Jira helpers for the BT deploy skill.
#
# Linking a Jira ticket needs NO credentials — a browse URL is project-agnostic:
#   jira_url("VE-271") -> https://buildtogether.atlassian.net/browse/VE-271
# So any key PROJ-123 found in a branch name, PR body or commit trailer can be hyperlinked, whatever
# project it belongs to (Vidira VE-*, the GUIN ERPNext Phase-2 project, etc.).
#
# The API token is ONLY needed to VALIDATE a key / fetch its summary+status+project, or to enumerate
# projects. It is read from the environment — NEVER hardcode or commit it:
#   export JIRA_BASE_URL="https://buildtogether.atlassian.net"   # default below
#   export JIRA_EMAIL="<atlassian-account-email>"
#   export JIRA_API_TOKEN="<token>"                              # rotate if it ever leaks
#
#   import sys; sys.path.insert(0, "<skill>/scripts")
#   from jira import jira_url, find_keys, get_issue, list_projects

import os
import re

BASE = os.environ.get("JIRA_BASE_URL", "https://buildtogether.atlassian.net").rstrip("/")

# A Jira key: 2+ upper-case/digit project code, a dash, digits. Word-bounded so "VE-271" matches but
# "UTF-8" (single-letter project) and "COVID-19" in prose don't get mislinked by accident.
KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d+\b")


def jira_url(key, base=None):
    return f"{(base or BASE).rstrip('/')}/browse/{key}"


def find_keys(text):
    # Every distinct Jira key in a string (branch name, PR title/body, commit message), in order.
    seen, out = set(), []
    for m in KEY_RE.findall(text or ""):
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


# The token's Atlassian account (not a secret — an email). Override with JIRA_EMAIL if it changes.
DEFAULT_EMAIL = "aman@buildtogether.co.in"


def _auth():
    email = os.environ.get("JIRA_EMAIL", DEFAULT_EMAIL)
    token = os.environ.get("JIRA_API_TOKEN")
    if not token:
        raise RuntimeError(
            "Set JIRA_API_TOKEN in the environment for Jira API calls "
            "(linking works without it; the token is only for validation/enrichment). "
            f"Account defaults to {DEFAULT_EMAIL}; override with JIRA_EMAIL."
        )
    return (email, token)


def get_issue(key, fields="summary,status,issuetype,project,labels,parent"):
    # Return {key, summary, status, type, project, labels, url} or None (404/no such key).
    # Requires JIRA_EMAIL + JIRA_API_TOKEN. Import requests lazily so linking never needs it.
    import requests

    r = requests.get(f"{BASE}/rest/api/3/issue/{key}", params={"fields": fields}, auth=_auth(), timeout=20)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    f = r.json().get("fields", {})
    return {
        "key": key,
        "summary": f.get("summary"),
        "status": (f.get("status") or {}).get("name"),
        "type": (f.get("issuetype") or {}).get("name"),
        "project": (f.get("project") or {}).get("key"),
        "labels": f.get("labels") or [],
        "url": jira_url(key),
    }


def list_projects():
    # All projects visible to the token account: [{key, name}, ...]. Use to confirm the GUIN
    # ERPNext Phase-2 project key vs Vidira's VE. Requires JIRA_EMAIL + JIRA_API_TOKEN.
    import requests

    out, start = [], 0
    while True:
        r = requests.get(
            f"{BASE}/rest/api/3/project/search",
            params={"maxResults": 50, "startAt": start},
            auth=_auth(), timeout=20,
        )
        r.raise_for_status()
        d = r.json()
        out += [{"key": p["key"], "name": p["name"]} for p in d.get("values", [])]
        if d.get("isLast", True):
            break
        start += len(d.get("values", []))
    return out
