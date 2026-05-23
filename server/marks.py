"""The "Mark done" store.

This is the ONLY way a session leaves the dashboard — there is no auto-
completion. It is server-owned and kept separate from events.jsonl, which stays
hook-append-only. Marking is a user action, not a session event.

A mark records the session's last-seen event timestamp. If a later event
arrives, the session reappears: any new event supersedes prior derived state.
"""

import json

from config import MARKS_PATH


def load_marks():
    """Return {session_id: {marked_at, last_event_ts}}; {} if none/unreadable."""
    try:
        with open(MARKS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(marks):
    with open(MARKS_PATH, "w", encoding="utf-8") as fh:
        json.dump(marks, fh, indent=2)
        fh.write("\n")


def mark_done(session_id, last_event_ts, marked_at):
    """Record a session as done at its current last-event timestamp."""
    marks = load_marks()
    marks[session_id] = {
        "marked_at": marked_at,
        "last_event_ts": last_event_ts,
    }
    _write(marks)


def unmark_done(session_ids):
    """Remove sessions from the done store — used to undo a Mark done."""
    marks = load_marks()
    for sid in session_ids:
        marks.pop(sid, None)
    _write(marks)
