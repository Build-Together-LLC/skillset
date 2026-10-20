# Catalogue — Activity Types and Projects per site

`activity_type` and `project` on a Timesheet row are Link fields: Frappe rejects any value that is not
an exact record name on THAT site. The catalogue is the list of valid values the build checks against.

## Which list a build uses (`ts_catalogue.resolve_catalogue`)

| Situation | Source | Effect |
|---|---|---|
| This site has a refreshed cache | `cache` | Activity Types and Projects validated against it |
| No cache, any other site | `none` | **no** Link validation; ONE warning (`UNVALIDATED_WARNING`); the site rejects unknown values on sync |
| Cache unreadable (corrupt, partial, count mismatch, newer schema) | error | build fails closed: `catalogue cache for <site> is unreadable — run catalogue refresh` |

There is no bundled list: a catalogue always comes from the site itself. A user with no API
credentials can still build the JSON and chat messages (source `none`).

## Commands

```
timesheet_suite.py catalogue refresh [--site S]
timesheet_suite.py catalogue list [--type activity|project] [--match TEXT]
```

- `refresh` reads from the profile's site with the env credentials (`FRAPPE_API_KEY`/`SECRET`, or user+password) and writes ONLY the local cache; the remote is read-only, so no confirm token is needed. It prints `site:`, counts with a diff against the previous cache (`+3 -1`) and the currency. `--site` is accepted only when the profile has no site yet, or equals the stored site; any other value exits 2 and points at `profile set --site NEW --confirm-site-change <origin>` — credentials never follow a flag to a new host.
- `list` searches what a build would validate against, and its first line says which: `source: cache erp.example.com (refreshed 2026-10-01) — 226 activity types, 12 projects` or `source: none`. `--match` is a case-insensitive substring (projects also match the short code).

## Queries (Frappe v15, `GET /api/resource/<DocType>`, `limit_page_length=0`)

- Activity Type: `filters=[["disabled","=",0]]`, `fields=["name","disabled"]`. An EMPTY result aborts the refresh with the cache untouched.
- Project: `filters=[["status","=","Open"]]`, `fields=["name","project_name","status"]`.
- Currency: `Company` where `name = <profile company>`, `["default_currency"]`; failure or no company is non-fatal (currency `null`; builds assume INR and warn).

## Permissions caveat

A project row is whatever THIS login may see:

- ERPNext gives the `Employee` role only `select` on Project. Frappe then returns just the search fields, so **`company` is silently absent from the rows** (and may be absent for any login). The catalogue therefore never reads `company` from Project rows: the cached `Company` column is empty.
- User Permissions narrow the list further. That is desired: it is the set the user can log against.
- A project missing from the cache may be Completed/Closed (only `Open` is fetched), hidden from this login, or created after the last refresh. Re-run `catalogue refresh` and, if it is still absent, ask the user.
- Cross-company setups (a project owned by one company, logged under another employee company) still work: there is no company filter.

## Cache layout

`$TIMESHEET_SUITE_HOME` (default `~/.config/timesheet-suite`)`/catalogues/<site_slug>/`, directory 0700, files 0600:

```
activity_types.csv   "Activity Type","Default Costing Rate","Default Billing Rate","Disabled"   (same columns on every site)
projects.csv         Project ID (docname / Link value),Short Code,Status,Company                (same columns on every site)
catalogue.json       {"schema": 1, "site": "https://erp.example.com", "fetched_at": "2026-10-01T10:00:00Z",
                      "counts": {"activity_types": 226, "projects": 12}, "currency": "INR"}
```

One cache per site (not per company). The site slug is the lowercase `host[:port]` with unsafe characters
turned into `_`, so a site string can never escape `catalogues/`. Nothing secret is stored: no
credentials, no employee data.

## Write protocol and failure modes

- Each file is written atomically (temp file + `os.replace`), CSVs first, **`catalogue.json` last**. On read, the meta `counts` must equal the number of rows in each CSV and `meta.site` must be the requested site.
- Crash before the meta landed: the old meta describes the old counts, so a half-new cache fails the count check (or, with no old cache, has no meta and reads as "no cache"). The next `refresh` repairs it.
- Meta names another site (hand-copied folder): ignored, treated as no cache.
- Corrupt/unreadable meta or CSV, wrong counts, schema newer than 1: `SuiteError` (fail closed) — never a silent fallback. `catalogue refresh` is the remedy and works even when the cache is corrupt.
- Fetch failure part-way (HTTP error, empty Activity Type list): nothing is written; the previous cache stays.
- `catalogue list` on a corrupt cache fails the same way as a build.
- Plain `http://` is refused for non-loopback sites (credentials would travel unencrypted); use an https hostname or tunnel to localhost.
