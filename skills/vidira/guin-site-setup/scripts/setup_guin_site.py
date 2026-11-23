#!/usr/bin/env python3
"""
setup_guin_site.py - create a fresh `guin.localhost` on the local Frappe v16 bench and install the
Guin (Retailers) app set (../apps.tsv). Thin launcher: all logic lives in the shared engine
    ../../vidira-site-setup/scripts/setup_vidira_site.py

Every engine flag works here unchanged:

    python3 ~/skillset/skills/vidira/guin-site-setup/scripts/setup_guin_site.py --dry-run
    python3 ~/skillset/skills/vidira/guin-site-setup/scripts/setup_guin_site.py
    python3 ~/skillset/skills/vidira/guin-site-setup/scripts/setup_guin_site.py --from install-apps
    python3 ~/skillset/skills/vidira/guin-site-setup/scripts/setup_guin_site.py --help

Defaults added for you: --apps-file <this skill>/apps.tsv  --site guin.localhost  --no-use
(--no-use: do not change the bench's default site, so other sites are unaffected; pass --site to override).
Python 3.9+, standard library only. Passwords are typed into bench's own prompts; this script never sees them.
"""
import os
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ENGINE = SKILL.parent / "vidira-site-setup" / "scripts" / "setup_vidira_site.py"

if not ENGINE.is_file():
    sys.exit(f"ERROR: shared engine not found: {ENGINE}\n"
             f"This skill needs the sibling folder 'vidira-site-setup' (same skills/ directory).")

os.execv(sys.executable, [sys.executable, str(ENGINE),
                          "--apps-file", str(SKILL / "apps.tsv"),
                          "--site", "guin.localhost",
                          "--no-use",
                          *sys.argv[1:]])
