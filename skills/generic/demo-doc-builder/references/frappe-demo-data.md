# Taking screenshots of a Frappe / ERPNext app without touching real data

Lessons from real runs. Follow them every time.

1. **Never screenshot a real site.** Create a throwaway site, install the app, seed demo data, drop the site afterwards.

   ```bash
   bench new-site demo-doc.localhost --db-root-password <root pw> --admin-password admin --mariadb-user-host-login-scope='%'
   bench --site demo-doc.localhost install-app <app> && bench --site demo-doc.localhost migrate
   ```
2. **Skip the setup wizard**, otherwise every page is "Get Started":
   `update \`tabInstalled Application\` set is_setup_complete=1;` and `System Settings.setup_complete = 1`, then `clear_cache`.
3. **`bench start` serves only the default site.** With `serve_default_site` and `default_site` set, every Host header
   (and `X-Frappe-Site-Name`) is answered by the default site. Serve the demo site on its own port:
   `bench --site demo-doc.localhost serve --port 9100` and shoot `http://localhost:9100`.
4. **The scheduler of the shared bench also runs for the demo site.** Demo records can trigger real jobs (for example a
   job that syncs sessions with an external service). Drop the demo site as soon as you have the shots.
5. **Login for screenshots** with a plain form fill and Enter on the password field; selectors on Frappe v16 are
   `#login_email` and `#login_password` (the button selector changes between versions).
6. **v16 URLs**: `/app/...` redirects to `/desk/...`. Wait for `domcontentloaded`, not `load` (socket.io polling never settles).
7. **Seed through the app's own functions**, not raw inserts, so list screens show what real data produces
   (for example child tables that a list query joins on).
8. **Users for access demos**: create a second user and log in with a second browser context (`contexts` in the plan).
9. **Run tests only on the throwaway site.** A test that calls a data-migrating function can move files on disk that a
   database rollback cannot undo.
10. **A data-scrubbing `after_migrate` hook** (common on UAT / local copies) blanks Password fields on every migrate.
    Enter secrets again after migrating, or keep them out of the page being documented.
11. Pixelate QR codes, API keys, tokens, e-mail addresses and phone numbers before use (`annotate.py` `pixelate`).
12. **No throwaway site?** (no database root password) Use the development site, but seed only fictional records, log every one in a
    manifest, save the settings pages you change, and tear it all down afterwards: `templates/frappe_seed_teardown.py`. Name everything
    `Demo ...` and `demo.<role>@example.com`, and filter list views by that prefix in the URL
    (`/app/<doctype>?name=%5B%22like%22%2C%22Demo%25%22%5D`) so real rows never appear.
13. **Do not run the product's tests on that site between seeding and shooting.** Tests commonly reset Single doctypes (settings pages) and
    wipe the demo configuration. If it happens, re-apply the demo settings and shoot again.
14. **Run seed and teardown scripts with `templates/frappe_run.py`**, not through `bench console`. The console reads piped lines as separate cells:
    a multi-line function, a variable set on the first line (`STEPS`) or `exec(..., globals())` can fail with `NameError`, and the first line can be lost.
    The runner does `frappe.init`, `frappe.connect` and `exec` with an explicit namespace: `python frappe_run.py <site> seed.py users,core,slots`
    from the `sites` folder with the bench's Python. Print lines that start with `RES` and grep for them: the output also holds warnings.
15. **Starting and stopping the dev server**: `bench --site <site> serve --port 8000` in the background, wait for `/api/method/ping`, stop it with the pid
    from `lsof -ti :8000`. Never use `pkill -f <pattern>` or `pgrep -f <pattern> | xargs kill`: the pattern also matches your own shell command and kills it (exit code 144).
16. **If bench prints "Redis Queue ... connection refused"**, start the redis servers the bench is configured for
    (`redis-server config/redis_cache.conf --daemonize yes`, same for `redis_queue.conf`) and try again.
17. **Selectors**: a form field is `[data-fieldname=<fieldname>]`; use that in `targets` so annotation boxes land on the right field. A Select field is set with the
    step `{"select": [selector, value]}`. A custom search box needs a fill, a wait and a click on its first option.
18. **Some forms render blank in a headless shot** (a script error in that doctype's form). Do not fight it: show a list view, an error log or a table instead.
19. **Show an e-mail the product queued**: read the Email Queue row, parse its MIME message, write the HTML part to a file and screenshot it with a `file://` base.
    Check recipients and any colleague lists before using it.
20. **Dates**: make seed dates relative to today so slots and bookings are in the future when you shoot, and say "as at <date>" in the document.
21. **Scripted login**: use the form login of a demo user. If you must use an API key for the administrator to shoot, create it for the shoot and remove it afterwards.
22. **Background jobs need a worker.** A button that only queues a job (bulk create, send, sync) does nothing until a worker runs, and the next
    steps find no data. Start a worker for that queue only (`bench --site <site> worker --queue long`), not all queues, so old jobs and emails do not fire.
    Wait for the job to finish before shooting the result. A job id may be de-duplicated for a while, so delete what a failed take created before the next take.
23. **A slow first load is normal on a dev site.** A desk page can take 10 seconds to reach `load` and 30 seconds when a service is down. Wait for
    `domcontentloaded`, allow a navigation timeout of 45 seconds, and check both Redis servers are running before a long shoot (they stop between sessions).
24. **Mirror the real site's configuration, not its data.** When the document must match UAT or production, read the live settings through the API
    (read only, with the key the owner gave you for that purpose), set the demo site to the same service names, policies and wording, and say in the
    document that the screens come from a demo copy of that setup. Do not create or change records on a shared site unless the owner asks, and when
    they do: dry run first, skip password and key fields, skip site-specific ids (for example a WhatsApp number id), and read the result back.
25. **Lists fill themselves with real people.** Host chips, link drop-downs, search lists, "Assigned To" and linked-record cards show real names and
    work emails even when the seed is fictional. Hide or rewrite them before shooting (see `security-and-privacy.md`, "Real data inside auto-filled lists").
