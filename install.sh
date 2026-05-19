#!/usr/bin/env bash
# Claude Code Session Tracker — hook installer.
#
# Wires the three hooks (SessionStart, Stop, PostToolUse) into
# ~/.claude/settings.json, all pointing at hooks/record_event.py with
# ABSOLUTE paths (GUI-spawned shells have a reduced PATH).
#
# Idempotent: re-running replaces our own entries, never duplicates them.
# Backs up settings.json before touching it.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SCRIPT="$SCRIPT_DIR/hooks/record_event.py"
SETTINGS="$HOME/.claude/settings.json"

PYTHON="$(command -v python3 || true)"
if [ -z "$PYTHON" ]; then
  echo "error: python3 not found on PATH" >&2
  exit 1
fi
if [ ! -f "$HOOK_SCRIPT" ]; then
  echo "error: hook script missing: $HOOK_SCRIPT" >&2
  exit 1
fi

mkdir -p "$HOME/.claude"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"

BACKUP="$SETTINGS.bak.$(date +%Y%m%d%H%M%S)"
cp "$SETTINGS" "$BACKUP"
echo "backed up settings.json -> $BACKUP"

PYTHON="$PYTHON" HOOK_SCRIPT="$HOOK_SCRIPT" SETTINGS="$SETTINGS" python3 - <<'PYEOF'
import json, os

python = os.environ["PYTHON"]
hook_script = os.environ["HOOK_SCRIPT"]
settings_path = os.environ["SETTINGS"]
command = f"{python} {hook_script}"

with open(settings_path) as fh:
    settings = json.load(fh)

hooks = settings.setdefault("hooks", {})

def install(event_name):
    # Drop any prior entry of ours, then append a fresh one.
    entries = [
        e for e in hooks.get(event_name, [])
        if not any(
            "record_event.py" in h.get("command", "")
            for h in e.get("hooks", [])
        )
    ]
    entries.append({"hooks": [{"type": "command", "command": command}]})
    hooks[event_name] = entries

for name in ("SessionStart", "Stop", "PostToolUse"):
    install(name)

with open(settings_path, "w") as fh:
    json.dump(settings, fh, indent=2)
    fh.write("\n")

print(f"wired SessionStart, Stop, PostToolUse -> {command}")
PYEOF

echo "done. open a NEW Claude Code session for the hooks to load."
