import argparse
import collections
import datetime
import json
import re
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("DOCBUILDER_SCRIPTS") or os.path.join(HERE, "..", "..", "document-builder", "scripts"))
from docbuilder import DocBuilder, _set_run
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
ALL_SECTIONS = ["summary", "time", "weekly", "daily", "delivered", "pending", "blocked", "docs"]


def args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--narrative", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sections", default=",".join(ALL_SECTIONS))
    return ap.parse_args()


def day_name(iso):
    return datetime.date.fromisoformat(iso).strftime("%a %d %b %Y")


def week_start(iso):
    d = datetime.date.fromisoformat(iso)
    return (d - datetime.timedelta(days=d.weekday())).isoformat()


def normalise_activity(name):
    parts = [p.strip().title() if p.strip().isupper() else p.strip() for p in re.split(r"\s*\+\s*|\s+and\s+", name or "Other")]
    return [p[:1].upper() + p[1:] for p in parts if p]


def activity_split(rows):
    out = collections.defaultdict(float)
    for r in rows:
        parts = normalise_activity(r["activity_type"])
        for p in parts:
            out[p] += r["hours"] / len(parts)
    return out


def clean_text(text):
    t = re.sub(r"\s+", " ", text or "")
    t = re.sub(r"Note: Activity logged as.*?(?=(Ref:|$))", "", t)
    t = re.sub(r"https://github\.com/([\w.\-]+/[\w.\-]+)/(?:pull|issues)/(\d+)", r"\1#\2", t)
    t = re.sub(r"Ref:\s*", "", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"\b(?:HR-EMP-\d+|EDU-[A-Z]+-[\d-]+|[A-Z]{2,5}\d{2,5})\b", "[id]", t)
    return re.sub(r"\s+", " ", t).strip(" .;")


def first_sentence(text, limit=175):
    t = clean_text(text)
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    s = m.group(1) if m else t
    return (s[:limit].rsplit(" ", 1)[0] + "...") if len(s) > limit else s


def plural(n, word):
    if n == 1:
        return f"{n} {word}"
    return f"{n} {word}es" if word.endswith(("x", "s")) else f"{n} {word}s"


def name_date(name):
    m = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", name)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d{2})-(\d{2})-(20\d{2})", name)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


PRIVATE_DOC = re.compile(r"compoff|overtime|holiday|salary|payslip|password|secret|credential|api[ _-]?key|timesheet", re.I)


def pr_token(p):
    return f"{p['repo']}#{p['number']}"


class Linker:
    def __init__(self, orgs, jira_host, jira_prefixes):
        alt = "|".join(re.escape(o) for o in sorted(orgs))
        jp = "|".join(re.escape(p) for p in sorted(jira_prefixes)) or "ZZZ"
        self.jira_host = jira_host
        self.token = re.compile(rf"(https?://[^\s,;)]+|(?:{alt})/[A-Za-z0-9_.\-]+(?:#\d+)?|\b(?:{jp})-\d+\b)")
        self.bare = re.compile(rf"((?:{alt})/[A-Za-z0-9_.\-]+)#(\d+)|(?<![\w/&])#(\d+)")

    def url(self, tok):
        if tok.startswith("http"):
            return tok
        m = re.match(r"([^#]+)#(\d+)$", tok)
        if m:
            return f"https://github.com/{m.group(1)}/pull/{m.group(2)}"
        if re.match(r"^[A-Z]+-\d+$", tok):
            return f"{self.jira_host}/browse/{tok}"
        return f"https://github.com/{tok}"

    def expand(self, text):
        last = [None]

        def sub(m):
            if m.group(1):
                last[0] = m.group(1)
                return m.group(0)
            return f"{last[0]}#{m.group(3)}" if last[0] else m.group(0)

        return self.bare.sub(sub, text)

    def link(self, doc):
        paragraphs = list(doc.paragraphs)
        for t in doc.tables:
            for row in t.rows:
                for cell in row.cells:
                    paragraphs += cell.paragraphs
        for p in paragraphs:
            self.paragraph(p)

    def paragraph(self, p):
        for run in list(p.runs):
            if not run.text or run.font.name == "Courier New":
                continue
            run.text = self.expand(run.text)
            if not self.token.search(run.text):
                continue
            size = run.font.size.pt if run.font.size else 12
            bold, italic = bool(run.font.bold), bool(run.font.italic)
            color = str(run.font.color.rgb) if run.font.color and run.font.color.type else "000000"
            anchor = run._element
            for i, piece in enumerate(self.token.split(run.text)):
                if not piece:
                    continue
                if i % 2 == 1:
                    clean = piece.rstrip(".")
                    el = self.make(p, clean, self.url(clean), size, bold, italic)
                    tail = piece[len(clean):]
                else:
                    new = p.add_run(piece)
                    _set_run(new, size=size, bold=bold, italic=italic, color=color)
                    el, tail = new._element, ""
                anchor.addnext(el)
                anchor = el
                if tail:
                    tr = p.add_run(tail)
                    _set_run(tr, size=size, bold=bold, italic=italic)
                    anchor.addnext(tr._element)
                    anchor = tr._element
            run._element.getparent().remove(run._element)

    def make(self, p, text, url, size, bold, italic):
        rid = p.part.relate_to(url, REL, is_external=True)
        h = OxmlElement("w:hyperlink")
        h.set(qn("r:id"), rid)
        h.set(qn("w:history"), "1")
        r = OxmlElement("w:r")
        rpr = OxmlElement("w:rPr")
        fonts = OxmlElement("w:rFonts")
        for slot in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            fonts.set(qn(slot), "Times New Roman")
        rpr.append(fonts)
        if bold:
            rpr.append(OxmlElement("w:b"))
        if italic:
            rpr.append(OxmlElement("w:i"))
        for tag, val in (("w:color", "0563C1"), ("w:sz", str(int(size * 2))), ("w:u", "single")):
            el = OxmlElement(tag)
            el.set(qn("w:val"), val)
            rpr.append(el)
        r.append(rpr)
        t = OxmlElement("w:t")
        t.set(qn("xml:space"), "preserve")
        t.text = text
        r.append(t)
        h.append(r)
        return h


class Digest:
    def __init__(self, data):
        self.d = data
        g = data.get("github", {})
        self.merged = g.get("prs_merged", [])
        self.unmerged = g.get("prs_closed_unmerged", [])
        self.opened = g.get("prs_opened", [])
        self.open_now = g.get("prs_open", [])
        self.reviewed = g.get("prs_reviewed", [])
        self.commits = g.get("commits", [])
        self.rows = (data.get("timesheet") or {}).get("rows", [])
        self.jira = data.get("jira", [])
        self.console = data.get("console") or {"by_day": {}, "themes": [], "runs": 0, "committed": 0, "days": 0}
        self.docs = [x for x in data.get("documents", []) if not PRIVATE_DOC.search(x["name"]) and (not name_date(x["name"]) or name_date(x["name"]) >= data["from"])]
        self.days = sorted({r["from_time"][:10] for r in self.rows} | {p["merged"] for p in self.merged} | {c["date"] for c in self.commits}
                           | {j["resolved"] for j in self.jira if j["resolved"] and data["from"] <= j["resolved"] <= data["to"]})
        self.days = [x for x in self.days if data["from"] <= x <= data["to"]]

    def calendar(self):
        start = datetime.date.fromisoformat(self.d["from"])
        end = datetime.date.fromisoformat(self.d["to"])
        out, cur = [], start
        while cur <= end:
            iso = cur.isoformat()
            if iso in self.days or cur.weekday() < 5:
                out.append(iso)
            cur += datetime.timedelta(days=1)
        return out

    def day(self, iso):
        rows = [r for r in self.rows if r["from_time"][:10] == iso]
        hours = sum(r["hours"] for r in rows)
        split = activity_split(rows)
        merged = [p for p in self.merged if p["merged"] == iso]
        commits = [c for c in self.commits if c["date"] == iso]
        resolved = [j for j in self.jira if j["resolved"] == iso]
        reviewed = [p for p in self.reviewed if p["updated"] == iso]
        docs = [x for x in self.docs if x["date"] == iso]
        con = (self.console.get("by_day") or {}).get(iso)
        top = sorted(rows, key=lambda r: -r["hours"])[:3]
        return {"iso": iso, "rows": rows, "hours": hours, "split": split, "merged": merged, "commits": commits, "resolved": resolved,
                "reviewed": reviewed, "docs": docs, "console": con, "top": top}

    def lines(self, iso, override=None):
        if override:
            return override
        x = self.day(iso)
        if not x["rows"] and not x["merged"] and not x["commits"]:
            return ["No time logged and no code activity (weekend, leave or holiday)."]
        out = []
        if x["rows"]:
            parts = ", ".join(f"{k} {v:.1f}" for k, v in sorted(x["split"].items(), key=lambda kv: -kv[1])[:5])
            out.append(f"Time: {x['hours']:.1f} h in total. {parts}.")
            seen, picks = set(), []
            for r in x["top"]:
                s = first_sentence(r["description"])
                if s and s[:40] not in seen:
                    seen.add(s[:40])
                    picks.append(s)
            out.append("Worked on: " + " ".join(p if p.endswith((".", "!", "?", "...")) else p + "." for p in picks[:3]))
        else:
            out.append("Time: no timesheet entry for this day.")
        bits = []
        if x["merged"]:
            toks = ", ".join(pr_token(p) for p in x["merged"][:6]) + (f" and {len(x['merged']) - 6} more" if len(x["merged"]) > 6 else "")
            bits.append(f"{plural(len(x['merged']), 'PR')} merged ({toks})")
        if x["commits"]:
            repos = collections.Counter(c["repo"].split("/")[1] for c in x["commits"]).most_common(3)
            bits.append(f"{plural(len(x['commits']), 'commit')} ({', '.join(f'{r} {n}' for r, n in repos)})")
        if x["resolved"]:
            bits.append("Jira closed " + ", ".join(j["key"] for j in x["resolved"]))
        if bits:
            out.append("Delivered: " + "; ".join(bits) + ".")
        extra = []
        if x["console"] and x["console"]["committed"]:
            extra.append(f"{plural(x['console']['committed'], 'production data fix')} run through the System Console")
        if x["reviewed"]:
            extra.append(f"reviewed {plural(len(x['reviewed']), 'teammate PR')}")
        if x["docs"]:
            extra.append("documents: " + ", ".join(d["name"].rsplit(".", 1)[0][:48] for d in x["docs"][:3]))
        if extra:
            out.append("Also: " + "; ".join(extra) + ".")
        return out

    def weeks(self):
        out = collections.OrderedDict()
        for iso in self.calendar():
            out.setdefault(week_start(iso), []).append(iso)
        return out

    def week_stats(self, days):
        s, e = days[0], days[-1]
        in_week = lambda d: s <= d <= e
        rows = [r for r in self.rows if in_week(r["from_time"][:10])]
        merged = [p for p in self.merged if in_week(p["merged"])]
        commits = [c for c in self.commits if in_week(c["date"])]
        done = [j for j in self.jira if j["resolved"] and in_week(j["resolved"])]
        repos = collections.Counter(p["repo"].split("/")[1] for p in merged).most_common(3)
        logged = len({r["from_time"][:10] for r in rows})
        return {"hours": sum(r["hours"] for r in rows), "days": logged, "merged": len(merged), "commits": len(commits), "done": len(done), "repos": repos,
                "split": activity_split(rows)}


def main():
    a = args()
    data = json.load(open(a.data))
    nar = json.load(open(a.narrative))
    want = [x.strip() for x in a.sections.split(",") if x.strip()]
    dg = Digest(data)
    orgs = {p["repo"].split("/")[0] for p in dg.merged + dg.open_now + dg.opened + dg.reviewed} | set(nar.get("extra_orgs", []))
    prefixes = {j["key"].split("-")[0] for j in dg.jira} | set(nar.get("jira_prefixes", []))
    linker = Linker(orgs, data.get("jira_host", ""), prefixes)

    f, t = data["from"], data["to"]
    d = DocBuilder(title=nar["title"], subtitle=nar.get("subtitle", ""),
                   meta={"Prepared by": nar["prepared_by"], "Prepared for": nar.get("audience", "Manager"), "Period": f"{day_name(f)} to {day_name(t)}",
                         "Generated": data["generated"], "Sources": nar.get("sources", "GitHub, timesheet, Jira, System Console log, documents folders"), "Status": nar.get("status", "v1.0")})

    hours = sum(r["hours"] for r in dg.rows)
    days_logged = len({r["from_time"][:10] for r in dg.rows})
    done_jira = [j for j in dg.jira if j["category"] == "Done" and j["resolved"] and f <= j["resolved"] <= t]
    repos_touched = {p["repo"] for p in dg.merged} | {c["repo"] for c in dg.commits}

    d.h1("Report Overview")
    d.table(["Measure", "Value", "Note"], [
        ["Working days with time logged", f"{days_logged}", f"{hours:.1f} hours, average {hours / max(days_logged, 1):.1f} h per day"],
        ["Pull requests merged", f"{len(dg.merged)}", f"{len(dg.unmerged)} more closed without merge (superseded or consolidated); {len(dg.opened)} opened in the period"],
        ["Commits on default branches", f"{len(dg.commits)}", f"across {len({c['repo'] for c in dg.commits})} repositories (lower bound)"],
        ["Repositories delivered to", f"{len(repos_touched)}", "all organisations combined"],
        ["Jira issues closed", f"{len(done_jira)}", f"{len([j for j in dg.jira if j['category'] != 'Done'])} still open"],
        ["Pull requests open now", f"{len(dg.open_now)}", "awaiting review or merge"],
        ["Teammate PRs reviewed", f"{len(dg.reviewed)}", "approximate: PRs reviewed and updated in the period"],
        ["Production data fixes (System Console)", f"{dg.console['committed']}", f"{dg.console['runs']} runs on {dg.console['days']} days"],
        ["Documents produced or updated", f"{len(dg.docs)}", "runbooks, BRDs, RCAs, comparisons, demo guides"],
    ], caption="Period at a glance", widths=[2.4, 1.0, 3.6])
    if "weekly" in want:
        rows = []
        for ws, days in dg.weeks().items():
            st = dg.week_stats(days)
            head = nar.get("weekly_headlines", {}).get(ws, "")
            rows.append([f"{day_name(days[0])[:10]} to {day_name(days[-1])[:10]}", f"{st['hours']:.1f}", str(st["merged"]), str(st["commits"]), str(st["done"]), head or "N/A"])
        d.table(["Week", "Hours", "PRs merged", "Commits", "Jira closed", "Headline"], rows, caption="Week by week", widths=[1.5, 0.6, 0.7, 0.7, 0.6, 2.9])

    if "summary" in want:
        d.h1("Consolidated Summary")
        for para in nar["summary"]:
            d.body(para)
        d.h2("What went well")
        for x in nar["went_well"]:
            d.bullet(x)
        d.h2("What is still pending")
        for x in nar["pending"]:
            d.bullet(x)
        d.h2("What is blocked or at risk")
        for x in nar["blocked_summary"]:
            d.bullet(x)

    if "time" in want:
        d.h1("Where the Time Went")
        total = collections.defaultdict(float)
        for r in dg.rows:
            for p in normalise_activity(r["activity_type"]):
                total[p] += r["hours"] / len(normalise_activity(r["activity_type"]))
        grand = sum(total.values()) or 1
        d.table(["Activity", "Hours", "Share"], [[k, f"{v:.1f}", f"{v / grand * 100:.0f}%"] for k, v in sorted(total.items(), key=lambda kv: -kv[1])[:12]],
                caption="Hours by activity (combined entries split equally)", widths=[3.0, 1.2, 1.2])
        if nar.get("time_notes"):
            for x in nar["time_notes"]:
                d.bullet(x)
        rows = []
        for ws, days in dg.weeks().items():
            st = dg.week_stats(days)
            top = ", ".join(f"{k} {v:.0f}" for k, v in sorted(st["split"].items(), key=lambda kv: -kv[1])[:3])
            rows.append([f"{day_name(days[0])[:10]} to {day_name(days[-1])[:10]}", f"{st['hours']:.1f}", str(st["days"]), top or "N/A"])
        d.table(["Week", "Hours", "Days logged", "Top activities (hours)"], rows, caption="Time by week", widths=[1.8, 0.8, 0.9, 3.5])

    if "daily" in want:
        d.h1("Day by Day")
        d.body("Each day lists where the time went, what was worked on, and what was delivered. Weekends without activity are omitted.", italic=True)
        overrides = nar.get("daily_overrides", {})
        cur_week = None
        for iso in dg.calendar():
            ws = week_start(iso)
            if ws != cur_week:
                cur_week = ws
                days = dg.weeks()[ws]
                st = dg.week_stats(days)
                d.h2(f"{day_name(days[0])[:10]} to {day_name(days[-1])[:10]}: {st['hours']:.1f} h, {plural(st['merged'], 'PR')} merged, {plural(st['commits'], 'commit')}, {st['done']} Jira closed")
                if nar.get("weekly_headlines", {}).get(ws):
                    d.body(nar["weekly_headlines"][ws], italic=True)
            x = dg.day(iso)
            d.h3(f"{day_name(iso)}" + (f" ({x['hours']:.1f} h)" if x["rows"] else ""))
            for line in dg.lines(iso, overrides.get(iso)):
                label, _, rest = line.partition(": ")
                if rest and label in ("Time", "Worked on", "Delivered", "Also"):
                    d.body(f"{label}: {rest}", align="left")
                else:
                    d.body(line, align="left")

    if "delivered" in want:
        d.h1("Delivered Work")
        if nar.get("themes"):
            d.h2("Highlights by theme")
            for th in nar["themes"]:
                d.h3(th["title"])
                d.body(th["text"])
                if th.get("refs"):
                    d.body("Evidence: " + ", ".join(th["refs"]), align="left")
        d.h2("All merged pull requests")
        by = collections.defaultdict(list)
        for p in dg.merged:
            by[p["repo"]].append(p)
        for repo, items in sorted(by.items(), key=lambda kv: -len(kv[1])):
            d.table(["Merged", "Pull request", "Title"], [[p["merged"], pr_token(p), p["title"][:120]] for p in sorted(items, key=lambda p: p["merged"])],
                    caption=f"{repo} ({len(items)})", widths=[0.9, 2.5, 3.6])
        if dg.unmerged:
            d.h2("Closed without merge")
            d.table(["Closed", "Pull request", "Title"], [[p["closed"], pr_token(p), p["title"][:120]] for p in sorted(dg.unmerged, key=lambda p: p["closed"])],
                    caption="Superseded, consolidated or replaced by another PR", widths=[0.9, 2.5, 3.6])
        if dg.console["themes"]:
            d.h2("Production data fixes (System Console)")
            d.table(["Fix", "Runs", "First", "Last"], [[t["title"], str(t["runs"]), t["first"], t["last"]] for t in dg.console["themes"]],
                    caption="Committed console runs by script", widths=[4.2, 0.6, 1.1, 1.1])
        if dg.reviewed:
            d.h2("Code reviews of teammates")
            who = collections.Counter(p["author"] for p in dg.reviewed)
            d.table(["Author", "PRs reviewed"], [[k, str(v)] for k, v in who.most_common()], caption="Reviews by author", widths=[3.5, 1.5])
            d.table(["Updated", "Pull request", "Title"], [[p["updated"], pr_token(p), p["title"][:110]] for p in sorted(dg.reviewed, key=lambda p: p["updated"])][:30],
                    caption="Reviewed pull requests (latest 30)", widths=[0.9, 2.5, 3.6])

    if "pending" in want:
        d.h1("Pending Work")
        today = datetime.date.fromisoformat(t)
        d.table(["Opened", "Age (days)", "Pull request", "Title"],
                [[p["created"], str((today - datetime.date.fromisoformat(p["created"])).days), pr_token(p), p["title"][:100] + (" (draft)" if p["draft"] else "")]
                 for p in sorted(dg.open_now, key=lambda p: p["created"])], caption="Open pull requests", widths=[0.9, 0.8, 2.4, 2.9])
        pend = [j for j in dg.jira if j["category"] != "Done"]
        if pend:
            d.table(["Issue", "Status", "Sprint", "Summary"], [[j["key"], j["status"], (j["sprints"] or ["N/A"])[-1], j["summary"][:90]] for j in sorted(pend, key=lambda j: j["key"])],
                    caption="Jira issues not yet done", widths=[0.8, 1.3, 1.3, 3.6])
        for x in nar.get("pending_detail", []):
            d.bullet(x)

    if "blocked" in want:
        d.h1("Blocked Items and Risks")
        d.table(["Item", "Why it is blocked or at risk", "What is needed", "Owner or ask"],
                [[b["item"], b["why"], b["need"], b["owner"]] for b in nar["blocked"]], caption="Blockers and risks", widths=[1.5, 2.3, 2.0, 1.2])

    if "docs" in want and dg.docs:
        d.h1("Documents Produced")
        d.table(["Date", "Document", "Folder"], [[x["date"], x["name"], f"{x['root']}/{x['folder']}"[:50]] for x in dg.docs], caption="Documents created or updated in the period", widths=[0.9, 4.2, 1.9])

    d.h1("Asks and Open Questions")
    for x in nar["asks"]:
        d.bullet(x)

    linker.link(d.doc)
    d.save(a.out)
    print(a.out)


if __name__ == "__main__":
    main()
