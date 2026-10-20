Sample Discord daily update — the exact format `build` produces.

All names, projects, repositories, links and records below are fictional — this file only shows the
shape of the output, not real data. It is generated from `assets/sample_spec.json`.

Rules shown by this example:
- First line: `Today's (MMM D) Update:`, followed directly by the numbered lines.
- One numbered point per time_log row, in the same order as the JSON.
- Each point: `<label as the user wrote it>: <summary> Ref [label](url), [label](url) (<Xh>)`.
- The label keeps the user's phrasing ("Coordination", "Code Review"); the JSON row carries the valid
  master type (`Communication`, `Code review`).
- Links are short `[label](url)` markdown, never raw URLs. They stay embedded only while the whole
  message fits in 2000 characters; past that they become plain labels, starting from the last line.
- Hours in parentheses at the end of each line: (2h), (1.5h), (0.5h).

---

Today's (Jan 15) Update:
1. Coding: Implemented the invoice export feature on the billing module and wired it to the download action Ref [PR-101](https://github.com/example-org/example-repo/pull/101) (2h)
2. Coding + Meeting: Paired with a teammate on the report builder — reviewed the draft component and agreed the filter layout Ref [PR-102](https://github.com/example-org/example-repo/pull/102) (1.5h)
3. Debugging: Failing scheduled job on staging traced to a null date field; applied a guard Ref [job log](https://erp.example.com/app/scheduled-job-log/EXAMPLE-JOB-001) (1h)
4. Deployment: Deployed billing and reporting changes to staging; smoke tests pass (1h)
5. Code Review: Reviewed + merged PR-103 Ref [PR-103](https://github.com/example-org/example-repo/pull/103) (0.5h)
6. Coordination: Weekly status to the project lead; one item blocked on client input (0.5h)
7. Meeting: Daily standup; picked up the next ticket Ref [Issue-57](https://github.com/example-org/example-repo/issues/57) (0.5h)

---

Point 6 shows "Coordination:" and point 5 "Code Review:" even though their JSON rows use the
`Communication` and `Code review` activity types — neither `Coordination` nor `Code Review` exists in
the master list. This message is 1003 characters.
