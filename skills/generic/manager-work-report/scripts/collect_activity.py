import collections
import csv
import datetime
import json
import os
import re
import sys

import requests

FROM = os.environ["FROM"]
TO = os.environ["TO"]
OUT = os.environ["OUT"]
GH = "https://api.github.com"
csv.field_size_limit(10**8)
ORGS = [o.strip().lower() for o in os.environ.get("GH_ORGS", "").split(",") if o.strip()]
REPOS = [r.strip().lower() for r in os.environ.get("GH_REPOS", "").split(",") if r.strip()]


def allowed(full_name):
    full = full_name.lower()
    if REPOS and full not in REPOS:
        return False
    if ORGS and full.split("/")[0] not in ORGS:
        return False
    return True


def scopes():
    if ORGS:
        return [f" org:{o}" for o in ORGS]
    return [""]


def search_prs(token, query):
    out, seen = [], set()
    for scope in scopes():
        for p in gh_paged(f"{GH}/search/issues", token, {"q": query + scope}, key="items"):
            repo = p["repository_url"].split("/repos/")[1]
            if (repo, p["number"]) in seen or not allowed(repo):
                continue
            seen.add((repo, p["number"]))
            out.append(p)
    return out


def gh_get(url, token, params=None, accept="application/vnd.github+json"):
    r = requests.get(url, headers={"Authorization": f"Bearer {token}", "Accept": accept}, params=params)
    if r.status_code == 403 and "rate" in r.text.lower():
        import time
        time.sleep(30)
        return gh_get(url, token, params, accept)
    return r


def gh_paged(url, token, params=None, key=None, cap=10):
    out, p = [], dict(params or {})
    p["per_page"] = 100
    for page in range(1, cap + 1):
        p["page"] = page
        r = gh_get(url, token, p)
        if r.status_code != 200:
            print("ERR", url, r.status_code, r.text[:100], file=sys.stderr)
            break
        items = r.json()[key] if key else r.json()
        out += items
        if len(items) < 100:
            break
    return out


def in_range(day):
    return bool(day) and FROM <= day[:10] <= TO


def github(accounts):
    result = {"prs_merged": [], "prs_closed_unmerged": [], "prs_opened": [], "prs_open": [], "prs_reviewed": [], "commits": []}
    seen_pr, seen_commit = set(), set()
    for login, token in accounts.items():
        items = search_prs(token, f"author:{login} type:pr updated:>={FROM}")
        for p in items:
            repo = p["repository_url"].split("/repos/")[1]
            key = (repo, p["number"])
            if key in seen_pr:
                continue
            seen_pr.add(key)
            merged_at = (p.get("pull_request") or {}).get("merged_at")
            row = {"account": login, "repo": repo, "number": p["number"], "title": p["title"], "state": p["state"],
                   "created": p["created_at"][:10], "closed": (p.get("closed_at") or "")[:10], "merged": (merged_at or "")[:10],
                   "url": p["html_url"], "labels": [l["name"] for l in p["labels"]], "comments": p.get("comments", 0)}
            if in_range(row["merged"]):
                result["prs_merged"].append(row)
            elif p["state"] == "closed" and in_range(row["closed"]):
                result["prs_closed_unmerged"].append(row)
            if in_range(row["created"]):
                result["prs_opened"].append(row)
        for p in search_prs(token, f"author:{login} type:pr state:open"):
            repo = p["repository_url"].split("/repos/")[1]
            result["prs_open"].append({"account": login, "repo": repo, "number": p["number"], "title": p["title"], "created": p["created_at"][:10], "updated": p["updated_at"][:10], "url": p["html_url"], "draft": p.get("draft", False)})
        for p in search_prs(token, f"reviewed-by:{login} -author:{login} type:pr updated:>={FROM}"):
            repo = p["repository_url"].split("/repos/")[1]
            result["prs_reviewed"].append({"account": login, "repo": repo, "number": p["number"], "title": p["title"], "author": p["user"]["login"], "updated": p["updated_at"][:10], "url": p["html_url"]})
        repos = gh_paged(f"{GH}/user/repos", token, {"affiliation": "owner,collaborator,organization_member", "sort": "pushed"})
        for repo in repos:
            if repo["pushed_at"][:10] < FROM or not allowed(repo["full_name"]):
                continue
            r = gh_get(f"{GH}/repos/{repo['full_name']}/commits", token, {"author": login, "since": FROM + "T00:00:00Z", "until": TO + "T23:59:59Z", "per_page": 100})
            if r.status_code != 200:
                continue
            for c in r.json():
                if c["sha"] in seen_commit:
                    continue
                seen_commit.add(c["sha"])
                result["commits"].append({"account": login, "repo": repo["full_name"], "sha": c["sha"][:10], "date": c["commit"]["author"]["date"][:10],
                                          "message": c["commit"]["message"].split("\n")[0][:140], "url": c["html_url"]})
    own = {login.lower() for login in accounts}
    for pr in result["prs_opened"] + result["prs_merged"]:
        token = accounts[next(l for l in accounts if l.lower() == pr["account"].lower())]
        for c in gh_paged(f"{GH}/repos/{pr['repo']}/pulls/{pr['number']}/commits", token):
            if c["sha"] in seen_commit:
                continue
            login = (c.get("author") or {}).get("login", "")
            day = c["commit"]["author"]["date"][:10]
            if login.lower() not in own or not in_range(day):
                continue
            seen_commit.add(c["sha"])
            result["commits"].append({"account": login, "repo": pr["repo"], "sha": c["sha"][:10], "date": day,
                                      "message": c["commit"]["message"].split("\n")[0][:140], "url": c["html_url"]})
    return result


def timesheet(host, user, pwd):
    s = requests.Session()
    r = s.post(f"{host}/api/method/login", data={"usr": user, "pwd": pwd})
    if r.status_code != 200:
        print("timesheet login failed", r.status_code, file=sys.stderr)
        return None
    heads = s.get(f"{host}/api/resource/Timesheet", params={"fields": json.dumps(["name", "start_date", "total_hours", "status", "docstatus"]),
                  "filters": json.dumps([["start_date", ">=", FROM], ["start_date", "<=", TO]]), "limit_page_length": 1000, "order_by": "start_date asc"}).json().get("data", [])
    rows = s.get(f"{host}/api/method/frappe.client.get_list", params={"doctype": "Timesheet Detail", "parent": "Timesheet",
                 "fields": json.dumps(["parent", "project", "project_name", "task", "activity_type", "hours", "from_time", "description"]),
                 "filters": json.dumps([["from_time", ">=", FROM], ["from_time", "<=", TO + " 23:59:59"]]), "limit_page_length": 5000}).json().get("message", [])
    return {"timesheets": heads, "rows": rows}


def jira(host, email, token):
    auth = (email, token)
    headers = {"Accept": "application/json"}
    issues, page_token = [], None
    jql = f'(assignee = currentUser() OR reporter = currentUser()) AND updated >= "{FROM}" ORDER BY updated DESC'
    while True:
        params = {"jql": jql, "maxResults": 100, "fields": "summary,status,issuetype,priority,created,updated,resolutiondate,labels,customfield_10020,customfield_10021,project"}
        if page_token:
            params["nextPageToken"] = page_token
        r = requests.get(f"{host}/rest/api/3/search/jql", auth=auth, headers=headers, params=params)
        if r.status_code != 200:
            print("jira failed", r.status_code, r.text[:150], file=sys.stderr)
            break
        page = r.json()
        issues += page.get("issues", [])
        page_token = page.get("nextPageToken")
        if not page_token or page.get("isLast"):
            break
    out = []
    for i in issues:
        f = i["fields"]
        out.append({"key": i["key"], "summary": f["summary"], "status": f["status"]["name"], "category": f["status"]["statusCategory"]["name"],
                    "type": f["issuetype"]["name"], "priority": (f.get("priority") or {}).get("name"), "project": f["project"]["key"],
                    "created": f["created"][:10], "updated": f["updated"][:10], "resolved": (f.get("resolutiondate") or "")[:10],
                    "sprints": [x.get("name") for x in (f.get("customfield_10020") or [])], "labels": f.get("labels", []),
                    "flagged": bool(f.get("customfield_10021")), "url": f"{host}/browse/{i['key']}"})
    return out


def console_log(path):
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8-sig")))
    mine = [r for r in rows if in_range(r["ID"].replace("Log on ", ""))]
    committed = [r for r in mine if r["Committed"] == "1"]

    def title(script):
        for line in script.split("\n"):
            line = line.strip()
            if line.startswith("#") and set(line) - set("#=-_ "):
                return clean(line.lstrip("# ").strip())
        first = script.strip().split("\n")[0]
        if "get_doc(" in first or "get_password" in script[:400]:
            return "Integration settings review (details withheld)"
        return clean(first)

    def clean(text):
        return re.sub(r"\d{6,}", "xxxx", text)[:110]

    themes = collections.OrderedDict()
    for r in sorted(committed, key=lambda r: r["ID"]):
        themes.setdefault(title(r["Script"]), []).append(r["ID"].replace("Log on ", "")[:10])
    by_day = collections.defaultdict(lambda: {"runs": 0, "committed": 0})
    for r in mine:
        day = r["ID"].replace("Log on ", "")[:10]
        by_day[day]["runs"] += 1
        by_day[day]["committed"] += r["Committed"] == "1"
    return {"by_day": by_day, "runs": len(mine), "committed": len(committed), "days": len({r["ID"].replace("Log on ", "")[:10] for r in mine}),
            "themes": [{"title": t, "runs": len(d), "first": d[0], "last": d[-1]} for t, d in themes.items()]}


def documents(dirs):
    skip = re.compile(r"key|secret|password|token|credential|backup|\.csv$|\.json$", re.I)
    found = []
    for base in dirs:
        for dp, dn, fn in os.walk(base):
            dn[:] = [d for d in dn if not d.startswith(".") and d not in ("node_modules", "__pycache__", "assets", "screenshots", "work")]
            for f in fn:
                if not f.lower().endswith((".docx", ".pdf", ".pptx", ".xlsx", ".md")) or skip.search(f):
                    continue
                p = os.path.join(dp, f)
                day = datetime.date.fromtimestamp(os.path.getmtime(p)).isoformat()
                if in_range(day):
                    found.append({"name": f, "folder": os.path.relpath(dp, base), "root": os.path.basename(base.rstrip("/")), "date": day, "path": p})
    return sorted(found, key=lambda x: (x["date"], x["name"]))


def main():
    data = {"from": FROM, "to": TO, "generated": datetime.date.today().isoformat()}
    if os.environ.get("GH_ACCOUNTS"):
        accounts = json.loads(os.environ["GH_ACCOUNTS"])
        if os.environ.get("GH_TOKEN_FROM_GH"):
            import subprocess
            accounts = {a: subprocess.run(["gh", "auth", "token", "--user", a], capture_output=True, text=True).stdout.strip() for a in accounts}
        data["github"] = github(accounts)
        g = data["github"]
        print("github: merged", len(g["prs_merged"]), "closed unmerged", len(g["prs_closed_unmerged"]), "opened", len(g["prs_opened"]), "open now", len(g["prs_open"]), "reviewed", len(g["prs_reviewed"]), "commits", len(g["commits"]))
    if os.environ.get("TS_HOST"):
        data["timesheet"] = timesheet(os.environ["TS_HOST"].rstrip("/"), os.environ["TS_USER"], os.environ["TS_PWD"])
        if data["timesheet"]:
            print("timesheet: sheets", len(data["timesheet"]["timesheets"]), "rows", len(data["timesheet"]["rows"]))
    if os.environ.get("JIRA_HOST"):
        data["jira"] = jira(os.environ["JIRA_HOST"].rstrip("/"), os.environ["JIRA_EMAIL"], os.environ["JIRA_TOKEN"])
        data["jira_host"] = os.environ["JIRA_HOST"].rstrip("/")
        print("jira: issues", len(data["jira"]))
    if os.environ.get("CONSOLE_CSV"):
        data["console"] = console_log(os.environ["CONSOLE_CSV"])
        print("console:", data["console"]["runs"], "runs,", data["console"]["committed"], "committed")
    if os.environ.get("DOCS_DIRS"):
        data["documents"] = documents([d for d in os.environ["DOCS_DIRS"].split(":") if d])
        print("documents:", len(data["documents"]))
    json.dump(data, open(OUT, "w"))


if __name__ == "__main__":
    main()
