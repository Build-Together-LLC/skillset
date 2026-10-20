# Seed and tear down fictional demo data on a Frappe site, with a manifest so nothing real is touched.
# Run through the bench console, so frappe is already connected:
#   echo "exec(open('/abs/path/run_seed.py').read(), globals())" | bench --site <site> console
# where run_seed.py is two lines:  STEPS = ["users", "records"]   then   exec(open('/abs/path/this_file.py').read(), globals())
# Use a wrapper file like that, not a multi-line paste: a paste is read as one block and STEPS is not visible inside it.
import json
import os

import frappe

MANIFEST = "/abs/path/manifest.json"          # every record created is written here, so teardown knows exactly what to remove
ORIGINALS = "/abs/path/originals.json"        # singles you change for the demo, saved before the first change
frappe.flags.in_test = True                   # sends run inline: nothing is left waiting in a job queue
created = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else []
PW = "Demo#Pass2026x"                         # example password for the demo users, never a real one


def log(doctype, name):
    created.append([doctype, name])
    json.dump(created, open(MANIFEST, "w"))


def make(doctype, **values):
    """Insert through the app's own code, so list screens show what real data produces."""
    doc = frappe.get_doc(dict(doctype=doctype, **values)).insert(ignore_permissions=True)
    log(doctype, doc.name)
    return doc


def save_original(doctype, fields):
    """Remember a single's current values before the demo changes them, and restore them at teardown."""
    saved = json.load(open(ORIGINALS)) if os.path.exists(ORIGINALS) else {}
    if doctype not in saved:
        doc = frappe.get_single(doctype)
        saved[doctype] = {f: doc.get(f) for f in fields}
        json.dump(saved, open(ORIGINALS, "w"))


def step(label, fn):
    try:
        out = fn()
        frappe.db.commit()
        print("RES ok", label, out if out is not None else "")
    except Exception as e:
        frappe.db.rollback()
        print("RES ERR", label, type(e).__name__, str(e)[:300])


def users():
    # demo.<role>@example.com, with only the roles the demo needs
    for who, roles in (("demo.admin", ["System Manager"]), ("demo.agent", ["Employee"])):
        email = f"{who}@example.com"
        user = frappe.get_doc(dict(doctype="User", email=email, first_name="Demo", send_welcome_email=0, enabled=1,
                                   new_password=PW, roles=[{"role": r} for r in roles])).insert(ignore_permissions=True)
        log("User", user.name)
    return "users"


def teardown():
    """Delete newest first, then print what is left. Link order matters: children and links before their parents."""
    for doctype, name in reversed(created):
        if frappe.db.exists(doctype, name):
            try:
                frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
            except Exception as e:
                print("RES skip", doctype, name, str(e)[:100])
    if os.path.exists(ORIGINALS):
        for doctype, values in json.load(open(ORIGINALS)).items():
            doc = frappe.get_single(doctype)
            for field, value in values.items():
                doc.set(field, value)
            doc.save(ignore_permissions=True)
    frappe.db.commit()
    print("RES leftovers", [(d, n) for d, n in created if frappe.db.exists(d, n)])


for _name, _fn in (("users", users),):
    if "STEPS" in globals() and _name in STEPS:
        step(_name, _fn)
if "STEPS" in globals() and "teardown" in STEPS:
    teardown()
