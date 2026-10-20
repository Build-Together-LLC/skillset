"""Record-and-replay loopback HTTP server for integration tests. Not a test module.

    with HttpFake() as site:
        site.reply("GET", "/api/method/frappe.auth.get_logged_user", {"message": "a@b.c"})
        client = FrappeClient(site.url, api_key="k", api_secret="s")
        ...
        site.requests            # [Recorded(method, path, query, headers, body)]
        site.requests_to("POST", "/api/resource/Timesheet")
        site.non_get()           # every recorded request that is not a GET

It models nothing about Frappe: the test sets the canned answer per (method, path) and asserts what the client sent.
An unconfigured route answers 404 with a Frappe-style JSON body, so a surprise call is visible, not silent.
"""
from __future__ import annotations

import json
import threading
import urllib.parse
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass
class Recorded:
	method: str
	path: str
	query: dict
	headers: dict
	body: str

	def json(self):
		return json.loads(self.body) if self.body else None


@dataclass
class Canned:
	status: int = 200
	body: object = field(default_factory=dict)
	headers: dict = field(default_factory=dict)


class HttpFake:
	def __init__(self):
		self.requests: list[Recorded] = []
		self.routes: dict[tuple[str, str], list[Canned]] = {}
		self._lock = threading.Lock()
		fake = self

		class Handler(BaseHTTPRequestHandler):
			protocol_version = "HTTP/1.1"

			def log_message(self, *args):  # keep test output quiet
				return

			def _serve(self):
				length = int(self.headers.get("Content-Length") or 0)
				body = self.rfile.read(length).decode() if length else ""
				parts = urllib.parse.urlsplit(self.path)
				record = Recorded(
					self.command,
					parts.path,
					dict(urllib.parse.parse_qsl(parts.query)),
					{key.lower(): value for key, value in self.headers.items()},
					body,
				)
				canned = fake._take(record)
				payload = canned.body if isinstance(canned.body, str) else json.dumps(canned.body)
				data = payload.encode()
				self.send_response(canned.status)
				self.send_header("Content-Type", "application/json")
				self.send_header("Content-Length", str(len(data)))
				for key, value in canned.headers.items():
					self.send_header(key, value)
				self.end_headers()
				self.wfile.write(data)

			do_GET = do_POST = do_PUT = do_DELETE = _serve

		self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
		self.server.daemon_threads = True
		self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)

	@property
	def url(self) -> str:
		return f"http://127.0.0.1:{self.server.server_address[1]}"

	def start(self) -> HttpFake:
		self.thread.start()
		return self

	def stop(self) -> None:
		self.server.shutdown()
		self.server.server_close()
		self.thread.join(timeout=5)

	def __enter__(self) -> HttpFake:
		return self.start()

	def __exit__(self, *exc) -> None:
		self.stop()

	# Configuration

	def reply(self, method: str, path: str, body=None, status: int = 200, headers: dict | None = None) -> None:
		"""Answer every `method path` with this response (the last one repeats). Call again to queue another answer."""
		with self._lock:
			self.routes.setdefault((method.upper(), path), []).append(Canned(status, {} if body is None else body, headers or {}))

	def _take(self, record: Recorded) -> Canned:
		with self._lock:
			self.requests.append(record)
			queue = self.routes.get((record.method, record.path))
			if not queue:
				return Canned(404, {"exc_type": "DoesNotExistError", "exception": f"no canned route {record.method} {record.path}"})
			return queue.pop(0) if len(queue) > 1 else queue[0]

	# Inspection

	def requests_to(self, method: str, path: str) -> list[Recorded]:
		return [r for r in self.requests if r.method == method.upper() and r.path == path]

	def non_get(self) -> list[Recorded]:
		return [r for r in self.requests if r.method != "GET"]
