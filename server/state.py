"""Derive per-session status from the event stream.

Status is confidence-tiered, not binary. The underlying signal cannot support a
clean binary call — a session busy inside one slow tool looks exactly like a
stalled one — so the tiers express graded confidence instead of asserting
certainty. See BRIEF.md.
"""

import os
from datetime import datetime, timezone

from config import LONG_SECONDS, SHORT_SECONDS

# Status constants, ordered by how loudly the dashboard surfaces them.
WAITING_ON_YOU = "waiting_on_you"
LIKELY_STALLED = "likely_stalled"
POSSIBLY_STUCK = "possibly_stuck"
ACTIVE = "active"

# Sort weight: lower = higher on the dashboard.
STATUS_ORDER = {
    WAITING_ON_YOU: 0,
    LIKELY_STALLED: 1,
    POSSIBLY_STUCK: 2,
    ACTIVE: 3,
}


def _parse_ts(value):
    """Parse an ISO-8601 timestamp; return None if it cannot be read."""
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _label_from_cwd(cwd):
    """Human label for a session — the repo/folder name. Keep it simple."""
    if not cwd:
        return "unknown"
    return os.path.basename(os.path.normpath(cwd)) or cwd


def derive_session(session_id, events, marks, now=None):
    """Derive one session's status dict, or None if it is marked done.

    `events` is this session's events in chronological (file) order.
    """
    if not events:
        return None
    now = now or datetime.now(timezone.utc)

    last = events[-1]
    last_ts = _parse_ts(last.get("ts"))
    if last_ts is None:
        return None  # cannot reason about a session with no readable time

    # Marked done — hidden, UNLESS an event arrived after the mark. Any new
    # event supersedes prior derived state; there is no auto-completion.
    mark = marks.get(session_id)
    if mark is not None:
        mark_ts = _parse_ts(mark.get("last_event_ts"))
        if mark_ts is not None and last_ts <= mark_ts:
            return None

    # Latest known cwd (events may carry None).
    cwd = next(
        (e.get("cwd") for e in reversed(events) if e.get("cwd")),
        None,
    )

    quiet_seconds = (now - last_ts).total_seconds()

    if last.get("type") == "turn_end":
        status = WAITING_ON_YOU
    elif quiet_seconds >= LONG_SECONDS:
        status = LIKELY_STALLED
    elif quiet_seconds >= SHORT_SECONDS:
        status = POSSIBLY_STUCK
    else:
        status = ACTIVE

    # Time in the current state is measured from the event that produced it —
    # the last event in every tier.
    seconds_in_state = (now - last_ts).total_seconds()

    return {
        "session_id": session_id,
        "label": _label_from_cwd(cwd),
        "cwd": cwd,
        "status": status,
        "since": last.get("ts"),
        "seconds_in_state": int(seconds_in_state),
        "event_count": len(events),
    }


def derive_all(grouped, marks, now=None):
    """Derive every session, drop the done ones, return dashboard-sorted.

    Sort: by status weight, then longest-in-state first within a tier so the
    most-neglected waiting session sits at the very top.
    """
    now = now or datetime.now(timezone.utc)
    sessions = []
    for session_id, events in grouped.items():
        derived = derive_session(session_id, events, marks, now=now)
        if derived is not None:
            sessions.append(derived)

    sessions.sort(
        key=lambda s: (STATUS_ORDER[s["status"]], -s["seconds_in_state"])
    )
    return sessions
