# Claude Code Session Tracker

A local, offline tool that surfaces the Claude Code sessions you've lost track
of — the ones **waiting on your reply** or **gone silent**.

Single machine. No sync, no accounts, no teams. Standard library only.

> Claude Code's built-in Agent View tracks background (`--bg`) sessions. This
> tracks the normal interactive tabs Agent View doesn't — the ones you actually
> lose.

## How it works

A local file is the source of truth; the server only reads it.

1. Three Claude Code hooks each append one compact JSON line to
   `~/.claude-sessions/events.jsonl`:
   - `SessionStart` — a session began.
   - `Stop` — Claude finished its turn; now waiting on you.
   - `PostToolUse` — liveness pulse; the session is working.
2. A local server reads that file and derives a status per session.
3. A web dashboard shows the prioritized list.

The file is truth, the server is a lens. If the server is off, hooks still
append and it catches up on the next read — zero data loss, zero added latency.

## Privacy

Hooks write **only** `session_id`, `cwd`, event type, timestamp, and (for
`SessionStart`) `source` + `transcript_path`. They never write your prompts,
tool inputs, tool outputs, or Claude's messages. Minimization happens in the
hook, before anything touches disk.

## Install

```sh
./install.sh        # wires the 3 hooks into ~/.claude/settings.json (backed up)
```

Open a **new** Claude Code session afterward — hooks load at session start.

## Run

```sh
./run.sh            # serves the dashboard at http://127.0.0.1:8787
```

## Status tiers

Status is confidence-tiered, not binary — on purpose (see "What it can and
can't tell you").

| Status | Meaning |
|---|---|
| `waiting_on_you` | Last event was `Stop`. Claude finished, waiting on you. |
| `active` | Recent tool activity. Working. Not flagged. |
| `possibly_stuck` | Quiet past a short threshold. Low confidence. |
| `likely_stalled` | Quiet past a long threshold. Higher confidence. |

Thresholds live in [config.py](config.py) and lean short — over-flagging is
cheap, missing a waiting session is not.

A session leaves the dashboard only when you click **Mark done**. There is no
auto-completion. If a marked-done session gets a new event, it reappears.

## What it can and can't tell you

- **"Claude finished and is waiting on you"** — detected reliably. `Stop` fires
  at the true end of a turn.
- **"Session went fully silent for a long time"** — detected; confidence grows
  with how long it has been quiet.
- **"Stalled *inside* one long-running tool"** — **not** reliably
  distinguishable from a session that is legitimately busy. `Stop` fires only
  at end-of-turn and `PostToolUse` goes silent while a single slow tool runs,
  so a stuck session and a busy one look identical. This is a platform
  limitation, not a shortcut. The tiered status says so honestly instead of
  guessing.

## Layout

```
hooks/record_event.py   one script, wired into all three hooks
server/                 reads events.jsonl, derives state, serves the dashboard
dashboard/index.html    the prioritized view
config.py               thresholds, paths, host/port
install.sh / run.sh     wire hooks / start server
BRIEF.md                the locked v1 spec
```
