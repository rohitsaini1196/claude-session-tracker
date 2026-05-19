"""Claude Code Session Tracker — configuration constants.

Thresholds are tunable, not magic numbers buried in logic. They lean SHORT on
purpose: over-flagging a session is cheap, missing one that waits on you is the
failure that matters.
"""

import os

# Source of truth — the hook-appended event log.
EVENTS_DIR = os.path.expanduser("~/.claude-sessions")
EVENTS_PATH = os.path.join(EVENTS_DIR, "events.jsonl")

# Server-owned store for explicit "Mark done" actions. NOT part of the event
# log: the log stays hook-append-only. Marks are user actions, kept separately.
MARKS_PATH = os.path.join(EVENTS_DIR, "marks.json")

# Confidence-tier thresholds, in seconds, measured from the last event.
#   quiet >= SHORT and no turn_end  -> possibly_stuck (low confidence)
#   quiet >= LONG  and no turn_end  -> likely_stalled (higher confidence)
SHORT_SECONDS = 90
LONG_SECONDS = 600

# Local dashboard server.
HOST = "127.0.0.1"
PORT = 8787
