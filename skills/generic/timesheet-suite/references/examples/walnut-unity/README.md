# Example: Walnut / Unity on Hybrowlabs Operate

A real setup, kept as a reference for onboarding another organisation. **Nothing here is a default** — a build
validates against the site's own cache (`catalogue refresh`), never against these files.

| | |
|---|---|
| Site | `https://operate.hybrowlabs.com` (Frappe/ERPNext, HRMS) |
| Company | the employer's company record on Operate (Link field `company`) |
| Default project | an internal `PROJ-####` ID; client projects use their descriptive name as the ID |
| Day start | `09:30`, UTC offset `+05:30` |
| Chat target | Discord (`discord_<date>.md`, pasted by hand or sent with `post`) |
| Code lives in | GitHub orgs `WalnutAppSuite`, `UnityAppSuite`, `hybrowlabs` (`--github-orgs`) |
| Local checkouts | `~/unity/walnut`, `~/unity/unity` (`sessions --roots …`) |

```bash
python3 scripts/timesheet_suite.py profile set --site operate.hybrowlabs.com \
  --employee HR-EMP-00001 --employee-name "Example Employee" --company "<company on Operate>" \
  --project PROJ-0019 --project-name "Walnut School" --start-time 09:30 --chat-targets discord \
  --github-users <login1>,<login2> --github-orgs WalnutAppSuite,UnityAppSuite,hybrowlabs
```

- `activity_types.csv` / `activity_types.md` — the Activity Type master as of the snapshot (hundreds of entries,
  mixed casing: `DEBUGGING`, `Code review`, `Coding + Meeting`). Link values must match exactly.
- `projects.csv` / `projects.md` — Project IDs. `project` on a row is the docname, not the short code.
- Operate marks weekly-off days (Sunday) as "attendance not marked Present"; a timesheet for one is refused
  with HTTP 417 until attendance exists. `build` warns about Sundays.
- Several GitHub logins commit to the same repos: pass all of them to `github` and it merges duplicates.
