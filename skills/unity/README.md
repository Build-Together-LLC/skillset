# Unity skills

Skills bound to the Unity / Walnut bench. They assume its apps, sites and team process, so they are
not part of the general set.

Source: https://github.com/UnityAppSuite/unity_dev_tools (`skills/`).

| Skill | What it does |
|---|---|
| `depmap` | Cross-app dependency map of the Unity bench, for planning features and placing new code |
| `graphify` | Internals of Unity / Walnut apps: functions, whitelisted APIs, hooks, controllers |
| `uat-employee-seeder` | Seeds test Employee records on a Walnut UAT site |
| `uat-prod-deploy-comparison` | UAT versus production deploy comparison for the Unity repos. The general version is `deploy-notes-comparison` |
| `unity-edu-fwd` | Unity Edu forwarding workflow |
| `unity-email-drafter` | Drafts client, vendor and internal email in the Unity Edu voice |
| `project-update` | Weekly update text for the Project Update DocType |
| `project-charter` | Project charter for Unity Edu projects |
| `project-plan-manager` | Project plan management |
| `doc-request-helper` | Helps raise and track document requests |

`timesheet-suite` and `manager-work-report` also exist in unity_dev_tools but are already in the
general `skills/` folder here, so they are not repeated.

Link them with `ln -s ~/skillset/skills/unity/* ~/.claude/skills/`.
