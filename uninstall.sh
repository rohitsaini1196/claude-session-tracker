#!/usr/bin/env bash
# Remove the Session Tracker hooks from ~/.claude/settings.json.
# Backs up settings.json first. Leaves your other hooks untouched.

set -euo pipefail

SETTINGS="$HOME/.claude/settings.json"
if [ ! -f "$SETTINGS" ]; then
  echo "nothing to do: $SETTINGS not found"
  exit 0
fi

BACKUP="$SETTINGS.bak.$(date +%Y%m%d%H%M%S)"
cp "$SETTINGS" "$BACKUP"
echo "backed up settings.json -> $BACKUP"

SETTINGS="$SETTINGS" python3 - <<'PYEOF'
import json, os

settings_path = os.environ["SETTINGS"]
with open(settings_path) as fh:
    settings = json.load(fh)

hooks = settings.get("hooks", {})
removed = 0
for event_name in ("SessionStart", "Stop", "PostToolUse"):
    kept = []
    for entry in hooks.get(event_name, []):
        if any("record_event.py" in h.get("command", "")
               for h in entry.get("hooks", [])):
            removed += 1
            continue
        kept.append(entry)
    if kept:
        hooks[event_name] = kept
    else:
        hooks.pop(event_name, None)

if not hooks:
    settings.pop("hooks", None)
else:
    settings["hooks"] = hooks

with open(settings_path, "w") as fh:
    json.dump(settings, fh, indent=2)
    fh.write("\n")

print(f"removed {removed} Session Tracker hook entr{'y' if removed == 1 else 'ies'}")
PYEOF

echo "done. your event log at ~/.claude-sessions/ is left intact — delete it manually if you want."
