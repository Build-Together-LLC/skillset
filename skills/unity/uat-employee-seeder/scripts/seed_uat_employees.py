#!/usr/bin/env python3
"""Seed sample Employees on a Walnut UAT / non-production Frappe site.

Flow: toggle Google Workspace creation OFF -> create employees (real names,
all required fields, no company_email/user_id) -> restore the flag. Google
account + Frappe User creation are both bypassed.

HARD SAFETY: refuses to run against production (erp.walnutedu.in). Stdlib only.
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

# --- Production guard -------------------------------------------------------
# Any host here is production and is NEVER written to.
PROD_HOSTS = {"erp.walnutedu.in"}
# Hosts positively known to be UAT/test. Anything outside this needs the
# explicit --i-confirm-non-prod flag.
KNOWN_UAT_HOSTS = {"unity-uat.m.frappe.cloud", "uat.unityedu.tech"}

# Built-in real-name roster: "First Last:Gender:DOB"
DEFAULT_NAMES = [
    "Rahul Sharma:Male:1995-01-10",
    "Priya Deshmukh:Female:1994-03-22",
    "Amit Patil:Male:1996-07-05",
    "Sneha Kulkarni:Female:1993-11-30",
    "Vikram Joshi:Male:1997-05-18",
    "Neha Gupta:Female:1995-09-14",
    "Arjun Rao:Male:1992-02-27",
    "Pooja Nair:Female:1998-06-19",
]


def host_of(base_url):
    return (urllib.parse.urlparse(base_url).hostname or "").lower()


def guard_not_prod(base_url, confirmed_non_prod):
    host = host_of(base_url)
    if not host:
        sys.exit("ABORT: could not parse a hostname from --base-url.")
    if host in PROD_HOSTS or "erp.walnutedu.in" in base_url:
        sys.exit(f"ABORT: {host} is PRODUCTION. This skill never writes to prod.")
    if host not in KNOWN_UAT_HOSTS and not confirmed_non_prod:
        sys.exit(
            f"ABORT: {host} is not a recognised UAT host {sorted(KNOWN_UAT_HOSTS)}.\n"
            "If you are certain this is a UAT/test site, re-run with --i-confirm-non-prod."
        )
    print(f"[guard] target host '{host}' is non-production. OK to proceed.")


class Client:
    def __init__(self, base_url, key, secret):
        self.base = base_url.rstrip("/")
        self.auth = f"token {key}:{secret}"

    def _req(self, method, path, params=None, body=None):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", self.auth)
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            payload = e.read().decode()
            try:
                d = json.loads(payload)
                sm = d.get("_server_messages")
                if sm:
                    msgs = "; ".join(json.loads(m).get("message", "") for m in json.loads(sm))
                    return {"_error": msgs or d.get("exception") or payload[:300]}
                return {"_error": d.get("exception") or payload[:300]}
            except Exception:
                return {"_error": payload[:300]}

    def get_single_value(self, doctype, field):
        r = self._req("GET", "/api/method/frappe.client.get_single_value",
                      params={"doctype": doctype, "field": field})
        return r.get("message")

    def set_single_value(self, doctype, fieldname, value):
        return self._req("POST", "/api/method/frappe.client.set_value",
                         params={"doctype": doctype, "name": doctype,
                                 "fieldname": fieldname, "value": value})

    def create_employee(self, fields):
        return self._req("POST", "/api/resource/Employee", body=fields)

    def get_list(self, doctype, filters, fields):
        return self._req("GET", "/api/method/frappe.client.get_list",
                         params={"doctype": doctype, "filters": json.dumps(filters),
                                 "fields": json.dumps(fields), "limit_page_length": 0})


FLAG_DT = "Google Service Account"
FLAG_FIELD = "create_employee_workspace"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--secret", required=True)
    ap.add_argument("--company", required=True)
    ap.add_argument("--holiday-list", required=True)
    ap.add_argument("--default-shift", required=True)
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--names", default="",
                    help='Optional "First Last:Gender:DOB,..." overriding the roster')
    ap.add_argument("--date-of-joining", default="2026-08-18")
    ap.add_argument("--i-confirm-non-prod", action="store_true")
    args = ap.parse_args()

    guard_not_prod(args.base_url, args.i_confirm_non_prod)

    roster = [n.strip() for n in args.names.split(",") if n.strip()] or DEFAULT_NAMES
    roster = roster[: args.count]
    if len(roster) < args.count:
        sys.exit(f"Need {args.count} names but only {len(roster)} available; pass more via --names.")

    c = Client(args.base_url, args.key, args.secret)

    original = c.get_single_value(FLAG_DT, FLAG_FIELD)
    print(f"[flag] current {FLAG_FIELD} = {original!r}")
    if original is None:
        sys.exit(f"ABORT: could not read {FLAG_DT}.{FLAG_FIELD}. Is this the right site?")

    created = []
    try:
        c.set_single_value(FLAG_DT, FLAG_FIELD, 0)
        now = c.get_single_value(FLAG_DT, FLAG_FIELD)
        print(f"[flag] set {FLAG_FIELD} -> {now!r} (Google bypass ON)")
        if str(now) != "0":
            sys.exit("ABORT: failed to disable the Google flag; not creating anything.")

        for i, entry in enumerate(roster, start=1):
            name, gender, dob = (entry.split(":") + ["", ""])[:3]
            first, _, last = name.partition(" ")
            last = last or "Sample"
            fields = {
                "first_name": first, "last_name": last, "employee_name": name.strip(),
                "gender": gender or "Male", "date_of_birth": dob or "1995-01-01",
                "date_of_joining": args.date_of_joining, "company": args.company,
                "status": "Active", "cell_number": f"90000000{i:02d}",
                "attendance_device_id": f"SEED{i:03d}",
                "holiday_list": args.holiday_list, "default_shift": args.default_shift,
                # company_email / user_id intentionally omitted -> no User, no Google
            }
            r = c.create_employee(fields)
            if "data" in r:
                created.append(r["data"]["name"])
                print(f"  OK  -> {r['data']['name']}  {r['data']['employee_name']} ({gender})")
            else:
                print(f"  ERR -> {name}: {r.get('_error')}")
    finally:
        c.set_single_value(FLAG_DT, FLAG_FIELD, original)
        restored = c.get_single_value(FLAG_DT, FLAG_FIELD)
        print(f"[flag] RESTORED {FLAG_FIELD} -> {restored!r}")
        if str(restored) != str(original):
            print(f"  !! WARNING: flag not restored to original {original!r} — fix manually!")

    # Verify no User leaked for the created employees
    if created:
        emp = c.get_list("Employee", [["name", "in", created]],
                         ["name", "employee_name", "company_email", "user_id"])
        leaked = [e for e in emp.get("message", []) if e.get("company_email") or e.get("user_id")]
        print(f"\n[verify] created {len(created)} employees; "
              f"{'NONE' if not leaked else len(leaked)} have company_email/user_id set.")
    print("\nReminder: rotate the API key you used — it may be in your shell history/transcript.")


if __name__ == "__main__":
    main()
