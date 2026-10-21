#!/usr/bin/env python3
"""
plan_manager.py — ERPNext Project Plan Manager

Commands:
  audit   <project>              Scan for issues (missing dates, deps, hierarchy)
  fix     <project>              Auto-fix date gaps, re-link sequential dependencies
  tree    <project>              Print task tree with dates + dependency arrows
  deps    <project>              Add depends_on links for sequential tasks
  create  <project> <template>  Create a new task plan from a YAML/JSON template

Usage:
  python3 plan_manager.py audit  SAL-ORD-<PHONE_NUMBER>
  python3 plan_manager.py fix    SAL-ORD-<PHONE_NUMBER>
  python3 plan_manager.py tree   SAL-ORD-<PHONE_NUMBER>
  python3 plan_manager.py deps   SAL-ORD-<PHONE_NUMBER>
"""

import sys, json, requests, argparse
from datetime import date, timedelta
from urllib.parse import quote

BASE = "https://operate.hybrowlabs.com"
AUTH = "token <ERPNEXT_TOKEN>"
HDR  = {"Authorization": AUTH}
HDR_FORM = {**HDR, "Content-Type": "application/x-www-form-urlencoded"}


# ─── API Helpers ────────────────────────────────────────────────────────────

def get_tasks(project):
    r = requests.get(f"{BASE}/api/resource/Task",
        params={
            "filters": json.dumps([["project","=",project]]),
            "fields":  json.dumps(["name","subject","parent_task","depends_on",
                                   "exp_start_date","exp_end_date","status","priority",
                                   "is_group","completed_on"]),
            "limit": 500,
            "order_by": "exp_start_date asc, name asc"
        }, headers=HDR)
    return r.json().get("data", [])


def get_task(tid):
    r = requests.get(f"{BASE}/api/resource/Task/{tid}", headers=HDR)
    return r.json().get("data", {})


def get_project(project):
    r = requests.get(f"{BASE}/api/resource/Project/{quote(project)}", headers=HDR)
    return r.json().get("data", {})


def update_task(tid, patch):
    r = requests.put(f"{BASE}/api/resource/Task/{tid}",
        data={"data": json.dumps(patch)}, headers=HDR_FORM)
    ok = r.status_code in (200, 201, 202)
    if not ok:
        print(f"    ⚠ Update {tid} failed: {r.text[:80]}")
    return ok


def add_dependency(tid, depends_on_tid):
    """Add a depends_on entry to a task."""
    full = get_task(tid)
    existing = full.get("depends_on", [])
    already = any(d.get("task") == depends_on_tid for d in existing)
    if already:
        return True
    existing.append({"task": depends_on_tid})
    return update_task(tid, {"depends_on": existing})


def create_task(subject, project, start, end, parent=None, priority="Medium", is_group=False):
    payload = {"doctype":"Task","subject":subject,"project":project,"status":"Open",
               "priority":priority,"exp_start_date":str(start),"exp_end_date":str(end),
               "is_group": 1 if is_group else 0}
    if parent:
        payload["parent_task"] = parent
    r = requests.post(f"{BASE}/api/resource/Task",
        data={"data": json.dumps(payload)}, headers=HDR_FORM)
    return r.json().get("data", {}).get("name")


def add_workdays(d, n):
    if isinstance(d, str): d = date.fromisoformat(d)
    count = 0
    while count < n:
        d += timedelta(days=1)
        if d.weekday() < 5: count += 1
    return d


def parse_date(s):
    if not s: return None
    try: return date.fromisoformat(s[:10])
    except: return None


# ─── Commands ───────────────────────────────────────────────────────────────

def cmd_tree(project):
    """Print the task tree with dates and dependency info."""
    tasks = get_tasks(project)
    if not tasks:
        print(f"No tasks found for project: {project}")
        return

    proj = get_project(project)
    print(f"\n📁 {proj.get('project_name', project)}")
    print(f"   Status: {proj.get('status')} | End: {proj.get('expected_end_date','?')}")
    print(f"   {BASE}/app/project/{project}\n")

    by_id = {t["name"]: t for t in tasks}
    # Build tree
    root_tasks = [t for t in tasks if not t.get("parent_task")]
    child_map  = {}
    for t in tasks:
        p = t.get("parent_task")
        if p:
            child_map.setdefault(p, []).append(t)

    def print_node(t, indent=0):
        prefix = "  " * indent
        name   = t["name"]
        subj   = t["subject"][:50]
        start  = t.get("exp_start_date","??")[:10] if t.get("exp_start_date") else "??"
        end    = t.get("exp_end_date","??")[:10]   if t.get("exp_end_date")   else "??"
        status = t.get("status","")
        icon   = "📌" if not t.get("parent_task") else "  ↳"
        print(f"{prefix}{icon} [{name}] {subj}")
        print(f"{prefix}     📅 {start} → {end}  [{status}]")
        for child in child_map.get(name, []):
            print_node(child, indent + 1)

    for t in root_tasks:
        print_node(t)

    parents  = [t for t in tasks if not t.get("parent_task")]
    children = [t for t in tasks if t.get("parent_task")]
    no_start = [t for t in tasks if not t.get("exp_start_date")]
    no_end   = [t for t in tasks if not t.get("exp_end_date")]
    print(f"\n📊 Summary: {len(tasks)} tasks | {len(parents)} parents | {len(children)} children")
    print(f"   Missing start date: {len(no_start)} | Missing end date: {len(no_end)}")


def cmd_audit(project):
    """Audit a project's tasks and report all issues."""
    tasks = get_tasks(project)
    proj  = get_project(project)
    p_end = parse_date(proj.get("expected_end_date"))

    print(f"\n🔎 Audit: {proj.get('project_name', project)}")
    print("=" * 60)

    issues = []

    by_id = {t["name"]: t for t in tasks}
    child_map = {}
    for t in tasks:
        p = t.get("parent_task")
        if p: child_map.setdefault(p, []).append(t)

    for t in tasks:
        tid   = t["name"]
        subj  = t["subject"]
        start = parse_date(t.get("exp_start_date"))
        end   = parse_date(t.get("exp_end_date"))
        par   = t.get("parent_task")

        if not start:
            issues.append(("❌ Missing start date", tid, subj))
        if not end:
            issues.append(("❌ Missing end date", tid, subj))
        if start and end and end <= start:
            issues.append(("❌ End ≤ Start", tid, f"{subj} ({start}→{end})"))
        if p_end and end and end > p_end:
            issues.append(("⚠ Task ends after project", tid, f"{subj} (task {end} > project {p_end})"))

        # Child dates must be within parent
        if par and par in by_id:
            par_start = parse_date(by_id[par].get("exp_start_date"))
            par_end   = parse_date(by_id[par].get("exp_end_date"))
            if par_start and start and start < par_start:
                issues.append(("⚠ Child starts before parent", tid, f"{subj}"))
            if par_end and end and end > par_end:
                issues.append(("⚠ Child ends after parent", tid, f"{subj} (child {end} > parent {par_end})"))

        # Parent task with no children (likely should have them)
        if not par and tid not in child_map:
            issues.append(("ℹ Parent task has no children", tid, subj))

    # Check sequential tasks missing deps
    parents_with_children = [tid for tid in child_map]
    for par_id in parents_with_children:
        siblings = sorted(child_map[par_id],
                          key=lambda t: t.get("exp_start_date") or "")
        for i, t in enumerate(siblings):
            if i == 0: continue
            prev = siblings[i-1]
            existing_deps = [d.get("task") for d in t.get("depends_on") or []]
            if prev["name"] not in existing_deps:
                issues.append(("ℹ Missing sequential dep", t["name"],
                                f"{t['subject'][:30]} → should depend on {prev['name']}"))

    if not issues:
        print("✅ No issues found!")
    else:
        for level, tid, msg in issues:
            print(f"  {level}: [{tid}] {msg}")
        print(f"\n  Total issues: {len(issues)}")

    return issues


def cmd_fix(project, dry_run=False):
    """Fix common issues: date gaps, parent bounds, sequential deps."""
    tasks  = get_tasks(project)
    by_id  = {t["name"]: t for t in tasks}
    proj   = get_project(project)

    child_map = {}
    for t in tasks:
        p = t.get("parent_task")
        if p: child_map.setdefault(p, []).append(t)

    print(f"\n🔧 Fixing: {proj.get('project_name', project)}"
          + (" [DRY RUN]" if dry_run else ""))
    print("=" * 60)

    fixes = 0

    # 1. Sequential dependencies within each parent group
    for par_id, children in child_map.items():
        siblings = sorted(children, key=lambda t: t.get("exp_start_date") or "")
        for i, t in enumerate(siblings):
            if i == 0: continue
            prev = siblings[i-1]
            existing_deps = [d.get("task") for d in t.get("depends_on") or []]
            if prev["name"] not in existing_deps:
                print(f"  ➕ Dep: [{t['name']}] {t['subject'][:35]} depends on [{prev['name']}]")
                if not dry_run:
                    if add_dependency(t["name"], prev["name"]):
                        fixes += 1
                else:
                    fixes += 1

    # 2. Parent-level sequential deps (module → module)
    root_tasks = sorted([t for t in tasks if not t.get("parent_task")],
                        key=lambda t: t.get("exp_start_date") or "")
    for i, t in enumerate(root_tasks):
        if i == 0: continue
        prev = root_tasks[i-1]
        existing_deps = [d.get("task") for d in t.get("depends_on") or []]
        if prev["name"] not in existing_deps:
            print(f"  ➕ Module dep: [{t['name']}] {t['subject'][:30]} depends on [{prev['name']}]")
            if not dry_run:
                if add_dependency(t["name"], prev["name"]):
                    fixes += 1
            else:
                fixes += 1

    # 3. Set is_group=1 on all parent tasks
    for t in tasks:
        if not t.get("parent_task") and not t.get("is_group"):
            print(f"  🏷  is_group=1 → [{t['name']}] {t['subject'][:40]}")
            if not dry_run:
                if update_task(t["name"], {"is_group": 1}):
                    fixes += 1
            else:
                fixes += 1

    # 4. Fix child tasks whose end date exceeds parent end date
    for par_id, children in child_map.items():
        par = by_id.get(par_id)
        if not par: continue
        par_end = parse_date(par.get("exp_end_date"))
        if not par_end: continue
        for child in children:
            child_end = parse_date(child.get("exp_end_date"))
            if child_end and child_end > par_end:
                print(f"  📅 Extend parent [{par_id}] end: {par_end} → {child_end}")
                if not dry_run:
                    if update_task(par_id, {"exp_end_date": str(child_end)}):
                        by_id[par_id]["exp_end_date"] = str(child_end)
                        fixes += 1
                else:
                    fixes += 1

    if fixes == 0:
        print("  ✅ Nothing to fix.")
    else:
        print(f"\n  ✅ {'Would apply' if dry_run else 'Applied'} {fixes} fix(es).")


def cmd_deps(project, dry_run=False):
    """Add depends_on links for sequential tasks (dry run by default)."""
    cmd_fix(project, dry_run=dry_run)


# ─── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="ERPNext Project Plan Manager")
    p.add_argument("command", choices=["audit","fix","tree","deps"])
    p.add_argument("project", help="Project ID e.g. SAL-ORD-<PHONE_NUMBER>")
    p.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = p.parse_args()

    if args.command == "tree":
        cmd_tree(args.project)
    elif args.command == "audit":
        cmd_audit(args.project)
    elif args.command in ("fix", "deps"):
        cmd_fix(args.project, dry_run=args.dry_run)
