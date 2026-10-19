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
14. **Console scripts**: pipe one line, `exec(open('/abs/run.py').read(), globals())`, into `bench --site <site> console`. Set variables such as `STEPS`
    inside a wrapper file, not on a second line of the pipe. Print lines that start with `RES` and grep for them: the console adds prompts and colours.
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

