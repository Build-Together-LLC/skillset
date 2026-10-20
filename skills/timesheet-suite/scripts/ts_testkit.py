"""Shared fixtures for the timesheet-suite tests. Not a test module."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROFILE = {
	"site": "https://erp.example.com",
	"employee_name": "Example Employee",
	"employee": "HR-EMP-00001",
	"company": "Example Company Pvt Ltd",
	"project": "PROJ-0019",
	"project_name": "Example Project",
	"start_time": "09:30:00",
	"chat_targets": ["discord"],
}
ACTIVITY_TYPES = {
	"Code review", "Coding", "Coding + Meeting", "Communication", "DEBUGGING", "Deployment", "Meeting", "Planning",
}
PROJECTS = {
	"PROJ-0019": {"short_code": "Example Project", "status": "Open", "company": "Example Company Pvt Ltd"},
	"PROJ-0002": {"short_code": "General Work", "status": "Open", "company": "Example Company Pvt Ltd"},
	"Acme Rollout": {"short_code": "ACME", "status": "Open", "company": "Example Company Pvt Ltd"},
	"Acme Phase 2": {"short_code": "ACME P2", "status": "Completed", "company": "Example Company Pvt Ltd"},
}


def entry(**overrides):
	base = {
		"label": "Coding",
		"activity_type": "Coding",
		"hours": 1.0,
		"summary": "Did the thing",
		"description": "Did the thing properly.",
		"links": [],
	}
	base.update(overrides)
	return base


def spec(entries, **overrides):
	base = {"date": "2026-09-08", "note": "A day of work.", "entries": entries}
	base.update(overrides)
	return base


def silent(*_args, **_kwargs):
	return None


class TempHome(unittest.TestCase):
	def setUp(self):
		tmp = tempfile.TemporaryDirectory()
		self.addCleanup(tmp.cleanup)
		patcher = mock.patch.dict(os.environ, {"TIMESHEET_SUITE_HOME": tmp.name})
		patcher.start()
		self.addCleanup(patcher.stop)
		self.home = Path(tmp.name)
