"""Derive per-session status from the event stream.

Status is confidence-tiered, not binary. The underlying signal cannot support a
clean binary call — a session busy inside one slow tool looks exactly like a
stalled one — so the tiers express graded confidence instead of asserting
certainty. See BRIEF.md.
"""

import os
from datetime import datetime, timezone

from config import (
    ENGAGED_GAP_SECONDS,
    FRESH_SECONDS,
    LONG_SECONDS,
    SHORT_SECONDS,
)
from server.ide import is_open

# Status constants, ordered by how loudly the dashboard surfaces them.
WAITING_ON_YOU = "waiting_on_you"
LIKELY_STALLED = "likely_stalled"
POSSIBLY_STUCK = "possibly_stuck"
JUST_FINISHED = "just_finished"
ACTIVE = "active"

# Sort weight: lower = higher on the dashboard. The sessions you might want
# to keep working on (active, just finished) sit on top so they are reachable
# without scrolling past a long historical list; waiting still surfaces loudly
# below them, with stuck/stalled at the bottom.
STATUS_ORDER = {
    ACTIVE: 0,
    JUST_FINISHED: 1,
    WAITING_ON_YOU: 2,
    POSSIBLY_STUCK: 3,
    LIKELY_STALLED: 4,
}

# Statuses where "most recent first" beats "longest neglect first" within a
# tier — for tabs you might still be driving, freshness is what you scan for.
_FRESH_FIRST = {ACTIVE, JUST_FINISHED}


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


_SPARK_BUCKETS = 15
_SPARK_BUCKET_SECONDS = 120  # 2 min × 15 = last 30 min on the sparkline


def _activity_buckets(events, now):
    """A 15-element histogram of event counts over the last 30 minutes."""
    buckets = [0] * _SPARK_BUCKETS
    window_start = now.timestamp() - _SPARK_BUCKETS * _SPARK_BUCKET_SECONDS
    for event in events:
        ts = _parse_ts(event.get("ts"))
        if ts is None:
            continue
        offset = ts.timestamp() - window_start
        if offset < 0:
            continue
        idx = int(offset // _SPARK_BUCKET_SECONDS)
        if 0 <= idx < _SPARK_BUCKETS:
            buckets[idx] += 1
    return buckets


def _engaged_seconds(events):
    """Sum of adjacent-event intervals shorter than ENGAGED_GAP_SECONDS.

    A proxy for "time actually spent on this tab" — long idle gaps are
    excluded, but tight tool bursts and turn cycles all count.
    """
    total = 0.0
    prev = None
    for event in events:
        ts = _parse_ts(event.get("ts"))
        if ts is None:
            continue
        if prev is not None:
            gap = (ts - prev).total_seconds()
            if 0 < gap < ENGAGED_GAP_SECONDS:
                total += gap
        prev = ts
    return int(total)


def derive_session(session_id, events, marks, open_ws=None, now=None):
    """Derive one session's status dict, or None if it is marked done.

    `events` is this session's events in chronological (file) order.
    `open_ws` is the set of workspace folders currently open in VSCode.
    """
    if not events:
        return None
    open_ws = open_ws or set()
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

    # When this session started — the timestamp of its session_start event.
    # Falls back to the first event seen if the session began before the
    # tracker was installed. Disambiguates multiple tabs sharing one repo.
    start_event = next(
        (e for e in events if e.get("type") == "session_start"),
        events[0],
    )
    started_at = start_event.get("ts")

    quiet_seconds = (now - last_ts).total_seconds()

    if last.get("type") == "turn_end":
        # A turn just ended. If it was recent you are probably still at that
        # tab; only an older turn_end is genuinely waiting on you.
        if quiet_seconds >= FRESH_SECONDS:
            status = WAITING_ON_YOU
        else:
            status = JUST_FINISHED
    elif quiet_seconds >= LONG_SECONDS:
        status = LIKELY_STALLED
    elif quiet_seconds >= SHORT_SECONDS:
        status = POSSIBLY_STUCK
    else:
        status = ACTIVE

    # Time in the current state is measured from the event that produced it —
    # the last event in every tier.
    seconds_in_state = (now - last_ts).total_seconds()

    # Focus link — only when the workspace is already open in VSCode, so the
    # click focuses an existing window and never spawns a new one.
    focusable = is_open(cwd, open_ws)

    return {
        "session_id": session_id,
        "label": _label_from_cwd(cwd),
        "cwd": cwd,
        "status": status,
        "started_at": started_at,
        "since": last.get("ts"),
        "seconds_in_state": int(seconds_in_state),
        "event_count": len(events),
        "engaged_seconds": _engaged_seconds(events),
        "last_event_type": last.get("type"),
        "activity": _activity_buckets(events, now),
        "focusable": focusable,
        "focus_url": ("vscode://file" + cwd) if (focusable and cwd) else None,
    }


def derive_all(grouped, marks, open_ws=None, now=None):
    """Derive every session, drop the done ones, return dashboard-sorted.

    Sort: by status weight, then longest-in-state first within a tier so the
    most-neglected waiting session sits at the very top.
    """
    now = now or datetime.now(timezone.utc)
    sessions = []
    for session_id, events in grouped.items():
        derived = derive_session(
            session_id, events, marks, open_ws=open_ws, now=now
        )
        if derived is not None:
            sessions.append(derived)

    def _within(s):
        # Active/just-finished: smallest seconds_in_state first (most recent).
        # Waiting/stuck/stalled: largest first (longest neglect).
        return (
            s["seconds_in_state"]
            if s["status"] in _FRESH_FIRST
            else -s["seconds_in_state"]
        )

    sessions.sort(key=lambda s: (STATUS_ORDER[s["status"]], _within(s)))
    return sessions
