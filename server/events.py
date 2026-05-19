"""Read the hook-appended event log.

The log is the source of truth. This module only reads it — never writes. It is
re-read in full on each request: the data is tiny (one line per turn) and a
stateless reader means the server can be off for hours and simply catch up on
the next read.
"""

import json

from config import EVENTS_PATH


def read_events():
    """Return all events as a list of dicts, oldest first.

    Tolerates a torn final line (a hook killed mid-write) and any other
    malformed line by skipping it — every well-formed prior event survives.
    """
    events = []
    try:
        with open(EVENTS_PATH, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue  # torn or malformed line — skip, keep the rest
                if isinstance(record, dict) and record.get("session_id"):
                    events.append(record)
    except FileNotFoundError:
        return []  # no hooks have fired yet
    return events


def events_by_session(events):
    """Group events by session_id, preserving file (chronological) order."""
    grouped = {}
    for event in events:
        grouped.setdefault(event["session_id"], []).append(event)
    return grouped
