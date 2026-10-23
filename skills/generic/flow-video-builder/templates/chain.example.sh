#!/bin/bash
# EXAMPLE of a scripted recording run for a flow that changes data. Copy it, change the paths, the site and the scene ids.
# Needs DEMO_USER and DEMO_PASSWORD in the environment (never in the file). A scene that changes data cannot be taken twice,
# so the whole run (reset, names, scenes, prep between scenes) is one command.
set -u
V=/path/to/project          # holds flow.json, flow.py, prep.py, names.json
S=/path/to/skills/flow-video-builder/scripts
BENCH=/path/to/bench
rec() { node $S/record.js --project $V "$@"; }
prep() { (cd $BENCH/sites && ../env/bin/python $V/prep.py "$@" 2>&1 | tail -2); }   # prep.py: reset | before_<scene> helpers, demo site only
cd $V
prep reset
# a naming series keeps counting after a reset: work out the names the new records will get and let flow.py read them
(cd $BENCH/sites && ../env/bin/python - <<'PY'
import frappe, json
frappe.init(site="demo.localhost", sites_path="."); frappe.connect()
cur = frappe.db.sql("select current from tabSeries where name='DOC-2026-'")[0][0]
json.dump({"FIRST": "DOC-2026-%05d" % (cur + 1), "SECOND": "DOC-2026-%05d" % (cur + 2)}, open("/path/to/project/names.json", "w"))
PY
)
python3 flow.py
rec s07 s08 s09 s10        # scenes that create and change records, in the order a person would do them
prep before_swap           # records that are not worth clicking through again
rec s11
echo CHAIN_DONE
