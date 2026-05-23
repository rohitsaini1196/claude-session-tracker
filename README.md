# Claude Code Session Tracker

A local, offline dashboard that surfaces the Claude Code sessions you've lost
track of — the ones **waiting on your reply** or **gone silent**.

Single machine. No sync, no accounts, no teams. No dependencies — Python
standard library only.

> **Why this exists:** Claude Code's built-in Agent View tracks background
> (`--bg`) sessions. This tracks the *normal interactive tabs* Agent View
> doesn't — the ones you open, walk away from, and forget.

## Demo

Run `./run.sh`, open <http://127.0.0.1:8787>. Sessions sort into tiers, the
ones needing you rise up, and a click jumps you back to the VSCode window.

<!-- Add a screenshot or GIF here: docs/demo.png -->

## Requirements

- **Python 3.8+** (standard library only — nothing to `pip install`)
- **Claude Code** with hook support
- macOS or Linux (VSCode focus links are best-effort on macOS)

## Install

```sh
git clone https://github.com/<you>/claude-code-session-tracker
cd claude-code-session-tracker
./install.sh        # wires 3 hooks into ~/.claude/settings.json (backed up first)
```

Open a **new** Claude Code session afterward — hooks load at session start.

## Run

```sh
./run.sh            # serves the dashboard at http://127.0.0.1:8787
```

## Uninstall

```sh
./uninstall.sh      # removes only our hooks; backs up settings.json; leaves your data
```

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
append and it catches up on the next read — **zero data loss, zero added turn
latency.**

## Privacy

Hooks write **only** `session_id`, `cwd`, event type, timestamp, and (for
`SessionStart`) `source` + `transcript_path`. They never write your prompts,
tool inputs, tool outputs, or Claude's messages. Minimization happens in the
hook, before anything touches disk — safe to point at private repos.

## The dashboard

- **Tiers, top to bottom:** Active · Recently finished · Waiting on you ·
  Possibly stuck · Likely stalled. The tabs you might still be driving sit on
  top; waiting still surfaces loudly below them.
- **Status chips** filter the list; **repo filter** narrows by name/path.
- **Collapsible sections** (state remembered) and **bulk "Mark all done."**
- **Click a row** → focuses that VSCode window (only when it's already open —
  never spawns a new one).
- **Per session:** engaged time, event count, when it opened, a 30-minute
  activity sparkline, and what it last did.
- **Undo** any "Mark done" for a few seconds.

A session leaves the dashboard only when you click **Mark done** — there is no
auto-completion. If a marked-done session gets a new event, it reappears.

## Status tiers

| Status | Meaning |
|---|---|
| `active` | Recent tool activity. Working. |
| `just_finished` | `Stop` fired recently — you're probably still on this tab. |
| `waiting_on_you` | `Stop` fired a while ago. Genuinely waiting. |
| `possibly_stuck` | Quiet past a short threshold. Low confidence. |
| `likely_stalled` | Quiet past a long threshold. Higher confidence. |

Thresholds live in [config.py](config.py) and lean short — over-flagging is
cheap, missing a waiting session is not.

## What it can and can't tell you

- **"Claude finished and is waiting on you"** — detected reliably. `Stop` fires
  at the true end of a turn.
- **"Session went fully silent for a long time"** — detected; confidence grows
  with how long it has been quiet.
- **"Stalled *inside* one long-running tool"** — **not** reliably
  distinguishable from a session that is legitimately busy. `Stop` fires only
  at end-of-turn and `PostToolUse` goes silent while a single slow tool runs,
  so a stuck session and a busy one look identical. A platform limitation, not
  a shortcut — the tiered status says so honestly instead of guessing.

## Layout

```
hooks/record_event.py   one script, wired into all three hooks
server/                 reads events.jsonl, derives state, serves the dashboard
  events.py             read the event log
  state.py              derive per-session status + tiers + engaged time
  ide.py                detect open VSCode windows (focus links)
  marks.py              the "Mark done" store
  app.py                stdlib HTTP server + JSON API
dashboard/index.html    the prioritized view
config.py               thresholds, paths, host/port
install.sh / uninstall.sh / run.sh
BRIEF.md                the design spec
```

## License

MIT — see [LICENSE](LICENSE).
