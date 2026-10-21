---
name: project-plan-manager
description: >
  Build and maintain ERPNext Project task hierarchies — parent/child tasks, Gantt
  date math, and module-driven implementation timelines — via the Frappe REST API.
  Use when asked to "create a project plan", set up tasks modelled on a reference
  project, or lay out a Gantt / task hierarchy / implementation timeline for a new
  ERPNext implementation.
---

# Project Plan Manager

**Trigger this skill when:**
- User says "create project plan" + references a project + lists modules
- User asks to "set up tasks like [reference project]"
- User mentions "project plan", "Gantt", "task hierarchy", or "implementation timeline"
- User provides module list for a new ERPNext implementation project

**Do NOT guess or create ad-hoc task structures. Always follow this skill.**

---

## Auth & Site

```
URL:  https://your-erpnext-site.com
Auth: token YOUR_API_KEY:YOUR_API_SECRET
```

## Script Location

```
skills/project-plan-manager/scripts/plan_manager.py
```

Always run from workspace root:
```bash
cd /path/to/workspace
```

---

## Creating a New Project Plan (FULL WORKFLOW)

### Step 1: Study the Reference Project

```bash
python3 skills/project-plan-manager/scripts/plan_manager.py tree "Reference-Project-Name"
```

Understand:
- How parent/child tasks are structured
- Date ranges and sequential flow
- Subtask naming conventions (e.g., "Module — Task Type")

### Step 2: Ensure Project End Date is Sufficient

Before creating tasks, extend the project end date to accommodate the full timeline:

```python
requests.put(f"{BASE}/api/resource/Project/{PROJECT}", headers=HDR,
    json={"expected_end_date": "2026-11-30"})
```

### Step 3: Create Tasks with Proper Date Math

**CRITICAL RULES:**
1. **Child dates must fall WITHIN parent date range** — ERPNext validates this strictly
2. **No gaps between subtasks** — end date of task N = day before start of task N+1
3. **Parent end date = last child end date + 1 buffer day**
4. **1-day tasks: start_date == end_date is valid** (audit warns but it's OK)

**Date Helper Functions:**
```python
from datetime import datetime, timedelta

def next_working(d):
    d += timedelta(days=1)
    while d.weekday() >= 5:  # Skip weekends
        d += timedelta(days=1)
    return d

def add_working_days(start, days):
    current = start
    for _ in range(days):
        current = next_working(current)
    return current
```

**Task Creation Pattern:**
```python
# 1. Calculate all child dates FIRST
child_dates = []
sub_start = module_start
for sub_name, days in subtasks:
    sub_end = add_working_days(sub_start, days - 1)  # days includes start
    child_dates.append((sub_name, sub_start, sub_end))
    sub_start = next_working(sub_end)  # Next task starts day after

# 2. Parent spans from first child start to last child end + buffer
mod_start = child_dates[0][1]
mod_end = add_working_days(child_dates[-1][2], 1)

# 3. Create parent FIRST (with is_group=True)
parent = create_task(mod_name, mod_start, mod_end, is_group=True)

# 4. Create children INSIDE parent bounds
for sub_name, s_start, s_end in child_dates:
    task = create_task(sub_name, s_start, s_end, parent=parent)
```

### Step 4: Wire Dependencies with `fix` Command

After creating all tasks, run:

```bash
python3 skills/project-plan-manager/scripts/plan_manager.py fix "<project_name>"
```

This auto-wires:
- Sequential deps within each parent group
- Module-to-module dependencies

### Step 5: Apply Colors for Gantt Visualization

```python
colors = {
    "TA00XXXX": "#4A90D9",  # Kickoff - Blue
    "TA00XXXX": "#2ECC71",  # Module 1 - Green
    "TA00XXXX": "#9B59B6",  # Module 2 - Purple
    # ... etc
}

for task_id, color in colors.items():
    requests.put(f"{BASE}/api/resource/Task/{task_id}", headers=HDR, json={"color": color})
    # Apply same color to children
    children = get_children(task_id)
    for child in children:
        requests.put(f"{BASE}/api/resource/Task/{child}", headers=HDR, json={"color": color})
```

**Recommended Color Palette:**
| Module Type | Color | Hex |
|-------------|-------|-----|
| Kickoff | Blue | #4A90D9 |
| Core Module | Green | #2ECC71 |
| Finance | Orange | #E67E22 |
| HR/Payroll | Red | #E74C3C |
| Inventory | Teal | #1ABC9C |
| Security | Dark Gray | #34495E |
| Compliance | Yellow | #F39C12 |
| UAT | Violet | #8E44AD |
| Go-Live | Success Green | #27AE60 |

### Step 6: Verify Final Structure

```bash
python3 skills/project-plan-manager/scripts/plan_manager.py tree "<project_name>"
python3 skills/project-plan-manager/scripts/plan_manager.py audit "<project_name>"
```

---

## Commands Reference

### `tree` — Print task hierarchy
```bash
python3 skills/project-plan-manager/scripts/plan_manager.py tree <project>
```

### `audit` — Find issues
```bash
python3 skills/project-plan-manager/scripts/plan_manager.py audit <project>
```

### `fix` — Wire dependencies
```bash
python3 skills/project-plan-manager/scripts/plan_manager.py fix <project>
python3 skills/project-plan-manager/scripts/plan_manager.py fix <project> --dry-run
```

---

## Deleting Tasks (When Cleaning Up)

ERPNext blocks deletion of linked tasks. **Delete in this order:**

```python
# 1. Clear ALL dependencies first
for task in all_tasks:
    requests.put(f"{BASE}/api/resource/Task/{task}", headers=HDR_FORM,
        data={"data": json.dumps({"depends_on": [], "parent_task": ""})})

# 2. Delete in reverse order (children first, then parents)
for task in reversed(all_tasks):
    requests.delete(f"{BASE}/api/resource/Task/{task}", headers=HDR)
```

---

## Example Project Structures

### ERPNext Implementation (Standard)
- 80-100 tasks | 14-16 parent modules | 70-85 children
- Structure: Kickoff → Accounts → CRM → Sales → Purchase → Inventory → Manufacturing → Quality → Support → HR → Recruitment → Performance → LMS → Integrations → UAT → Go-Live

### School/Education Implementation
- 80-90 tasks | 10-12 parent modules | 70-80 children
- Structure: Kickoff → Attendance/SIS → Fees/Student → Accounting → Inventory/Asset → HR/Payroll → Security → Compliance → UAT → Go-Live

---

## Common Pitfalls

1. **InvalidDates error** — Child task dates exceed parent bounds. Always calculate parent range to encompass all children.

2. **LinkExistsError on delete** — Tasks have depends_on links. Clear deps before deleting.

3. **NestedSet validation** — Can't delete parent with children. Unlink children first.

4. **Project end date too early** — Extend project.expected_end_date before creating tasks that go beyond it.

5. **Forgetting colors** — Always apply module colors at the end for better Gantt visualization.

---

## Typical Module Structure (ERPNext Implementation)

Each module typically has these subtask types:
- Process Discovery (1-2 days)
- BRD & Wireframes (2-4 days)
- Configuration (varies)
- Data Upload/Migration (1-2 days)
- Training (1-2 days)
- Reports & Dashboards (1-2 days)

Standard phases:
1. **Kickoff** — Charter, SOW, AS-IS/TO-BE, Sign-off
2. **Module Work** — Discovery → BRD → Config → Training per module
3. **UAT** — Test Plan → Execution → Bug Fixes → Performance → Sign-off
4. **Go-Live** — Migration → Cutover → Verification → Hypercare (2 weeks) → Closure
