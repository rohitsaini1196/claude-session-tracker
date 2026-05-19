"""Claude Code Session Tracker — local dashboard server.

A long-lived local process that READS events.jsonl and serves a dashboard. It
is a lens, not a source of truth: if it is off, hooks still append and it
catches up on the next read. Standard library only — no dependencies.

Run:  python3 -m server.app      (from the repo root)
"""

import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Make the repo root importable whether launched as a module or a script.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from config import HOST, PORT  # noqa: E402
from server.events import events_by_session, read_events  # noqa: E402
from server.marks import load_marks, mark_done  # noqa: E402
from server.state import ACTIVE, WAITING_ON_YOU, derive_all  # noqa: E402

DASHBOARD_HTML = os.path.join(REPO_ROOT, "dashboard", "index.html")


def build_payload():
    """Read the log, derive sessions, return the dashboard JSON payload."""
    grouped = events_by_session(read_events())
    marks = load_marks()
    sessions = derive_all(grouped, marks)

    counts = {}
    for session in sessions:
        counts[session["status"]] = counts.get(session["status"], 0) + 1

    waiting = counts.get(WAITING_ON_YOU, 0)
    active = counts.get(ACTIVE, 0)
    if waiting:
        headline = f"{waiting} waiting on you"
    elif sessions:
        headline = f"Nothing waiting — {active} active"
    else:
        headline = "No sessions tracked yet"

    return {
        "headline": headline,
        "counts": counts,
        "sessions": sessions,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def last_event_ts_for(session_id):
    """The timestamp of a session's most recent event, or None."""
    events = events_by_session(read_events()).get(session_id)
    if not events:
        return None
    return events[-1].get("ts")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code, obj):
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json")

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            try:
                with open(DASHBOARD_HTML, "rb") as fh:
                    self._send(200, fh.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(404, b"dashboard/index.html missing", "text/plain")
        elif self.path == "/api/sessions":
            self._send_json(200, build_payload())
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/done":
            self._send(404, b"not found", "text/plain")
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            session_id = body["session_id"]
        except (json.JSONDecodeError, KeyError, TypeError):
            self._send_json(400, {"error": "session_id required"})
            return

        last_ts = last_event_ts_for(session_id)
        if last_ts is None:
            self._send_json(404, {"error": "unknown session_id"})
            return

        mark_done(
            session_id,
            last_event_ts=last_ts,
            marked_at=datetime.now(timezone.utc).isoformat(),
        )
        self._send_json(200, {"ok": True})

    def log_message(self, *args):
        pass  # quiet — this is a local single-user tool


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"session tracker dashboard → http://{HOST}:{PORT}")
    print("reading", os.path.expanduser("~/.claude-sessions/events.jsonl"))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
