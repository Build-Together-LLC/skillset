# Example: Build Together (`buildtogether.frappe.cloud`)

A small Frappe Cloud site (Frappe/ERPNext/HRMS v16). Read from the live site with a read-only call; the CSVs here
are that snapshot in the same format `catalogue refresh` caches.

| | |
|---|---|
| Site | `https://buildtogether.frappe.cloud` |
| Company | `BuildTogether` (INR) |
| Employees | `HR-EMP-0000N`; several have no `user_id`, so `profile resolve` finds only those linked to a login |
| Activity Types | 5: Communication, Execution, Planning, Proposal Writing, Research (no billing rates) |
| Projects | 1 open project |
| Timesheet | submittable, `naming_series` `TS-.YYYY.-`, **no workflow**, no custom fields beyond `salary_slip` |
| Code lives in | GitHub orgs `Vidira-Innovations`, `Build-Together-LLC` |
| Local checkouts | apps under `~/personal/buildtogether/apps` (`sessions --roots …`) |

```bash
python3 scripts/timesheet_suite.py profile set --site buildtogether.frappe.cloud \
  --employee HR-EMP-00001 --employee-name "<name on the Employee record>" --company BuildTogether \
  --project PROJ-0001 --project-name "<project name>" --start-time 09:30 --chat-targets discord \
  --github-users <login> --github-orgs Vidira-Innovations,Build-Together-LLC

FRAPPE_API_KEY=… FRAPPE_API_SECRET=… python3 scripts/timesheet_suite.py catalogue refresh
```

- With only five Activity Types, map by intent: coding, debugging, testing and deployment → `Execution`;
  standups and calls → `Communication`; design and estimates → `Planning`; reading and spikes → `Research`;
  proposals → `Proposal Writing`. State each remap in the closing ⚠️ list.
- Credentials: one site API key + secret, exported in the shell, never pasted into the chat or a file.
- A Frappe Cloud site has no Sunday attendance rule by default, but HRMS can still be configured to enforce one;
  trust the server's 417 over this note.
