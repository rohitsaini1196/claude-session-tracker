#!/usr/bin/env python3
"""Claude Code Session Tracker — event-recording hook.

ONE script, wired into three hooks (SessionStart, Stop, PostToolUse). Reads the
hook JSON payload from stdin, extracts a minimal set of fields, and appends one
compact JSON line to ~/.claude-sessions/events.jsonl.

Design rules (locked, see BRIEF.md):
  - Local file append only. No network. No latency added to a turn.
  - Privacy: write ONLY the fields below. NEVER write prompt, tool_input,
    tool_response, or last_assistant_message — those carry code and prompts.
  - Key everything on session_id, never cwd (tabs share a cwd).
  - Must never break a session: any failure exits 0 silently.
"""

import json
import os
import sys
from datetime import datetime, timezone

EVENTS_DIR = os.path.expanduser("~/.claude-sessions")
EVENTS_PATH = os.path.join(EVENTS_DIR, "events.jsonl")

# Map the Claude Code hook name -> our event type.
EVENT_TYPE = {
    "SessionStart": "session_start",
    "Stop": "turn_end",
    "PostToolUse": "tool_activity",
}


def main() -> None:
    raw = sys.stdin.read()
    payload = json.loads(raw)

    hook_name = payload.get("hook_event_name", "")
    event_type = EVENT_TYPE.get(hook_name)
    if event_type is None:
        return  # unknown hook — nothing to record

    record = {
        "type": event_type,
        "hook_event_name": hook_name,
        "session_id": payload.get("session_id"),
        "cwd": payload.get("cwd"),
        "ts": datetime.now(timezone.utc).isoformat(),
    }

    # SessionStart-only fields. These let a future opt-in feature locate the
    # transcript; they carry no code or prompt content.
    if hook_name == "SessionStart":
        record["source"] = payload.get("source")
        record["transcript_path"] = payload.get("transcript_path")

    # One compact line. append mode + a single write() is atomic for lines
    # shorter than PIPE_BUF, so concurrent tabs never interleave.
    line = json.dumps(record, separators=(",", ":")) + "\n"
    os.makedirs(EVENTS_DIR, exist_ok=True)
    with open(EVENTS_PATH, "a", encoding="utf-8") as fh:
        fh.write(line)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # A hook must never break the session. Swallow everything, exit 0.
        pass
    sys.exit(0)
