"""Run a script inside a Frappe site without `bench console`. The console reads piped lines as separate cells, so multi-line
functions, variables set on an earlier line and `exec(..., globals())` can fail with NameError. This runner does not.

    cd <bench>/sites && source ../env/bin/activate
    python frappe_run.py <site> <script.py> [STEP1,STEP2]

The script sees `frappe` (connected, user Administrator) and `STEPS` (a list from the optional third argument).
Commit inside your script with frappe.db.commit(); the runner commits once more at the end.
Print lines starting with RES and grep for them: the output also contains warnings.
"""
import os
import sys

import frappe

site, script = sys.argv[1], sys.argv[2]
frappe.init(site=site, sites_path=os.getcwd())
frappe.connect()
frappe.set_user("Administrator")
env = {"frappe": frappe, "STEPS": sys.argv[3].split(",") if len(sys.argv) > 3 else [], "__name__": "frappe_run"}
exec(compile(open(script).read(), script, "exec"), env)
frappe.db.commit()
frappe.destroy()
