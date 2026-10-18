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
