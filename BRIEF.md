# Build: Claude Code Session Tracker — v1

## The problem

I open many Claude Code sessions (mostly VSCode tabs) and lose track of ones that are **waiting on my reply** or have **gone silent**. Build a local, offline tool that surfaces those. Single machine. No sync, no accounts, no teams.

## How it works (architecture — locked, do not redesign)

**A local file is the source of truth. The server only reads it.**

Three Claude Code hooks (documented API, `type: command`, **absolute paths** — GUI shells have reduced PATH) each append ONE compact JSON line to `~/.claude-sessions/events.jsonl`:

| Hook | Meaning | Record |
|---|---|---|
| `SessionStart` | A session began (zero-input registration). Record the `source` field (`startup` vs `resume`). | `session_id`, `cwd`, `source`, `transcript_path`, timestamp |
| `Stop` | Reliable "Claude finished its turn, now waiting on the human." | `session_id`, `cwd`, timestamp |
| `PostToolUse` | Liveness pulse — session is actively working. | `session_id`, `cwd`, timestamp |

Each hook is a tiny script: read JSON from stdin, extract only the fields above, append one line. **No network calls. Local file only.** This guarantees zero data loss and zero added turn latency if the server is off.

**Privacy (this will be open-sourced, pointed at private repos):** write ONLY the fields listed. NEVER write `prompt`, `tool_input`, `tool_response`, or `last_assistant_message` — those contain code and prompts. Minimize at the hook, before disk.

**Key everything on `session_id`. Never on `cwd`** — multiple tabs share a `cwd` (verified).

## State logic (server reads the file, derives per-session status)

Status is **confidence-tiered, not binary** — this is required, not optional. The signal cannot support a clean binary call (a session busy inside one slow tool is genuinely indistinguishable from a stalled one), so express graded confidence instead of asserting certainty.

- `waiting_on_you` — last event is `Stop`, nothing after. Reliable, high-confidence. Surface prominently, top of list.
- `active` — recent `PostToolUse`, no `Stop` after. Working. Don't flag.
- `possibly_stuck` (low confidence) — no `Stop`, no `PostToolUse` for a SHORT threshold. Show, low weight, honest copy ("quiet a while — may be busy in a long task or stuck").
- `likely_stalled` (higher confidence) — none for a LONG threshold. Surface loudly.
- Thresholds = config constants, not hardcoded. Lean SHORT (over-flagging is cheap; missing a waiting session is fatal).
- Any new event supersedes prior derived state. **No auto-completion ever** — only the user clicking "Mark done" removes a session.

## The surface (v1)

A single local web dashboard served by the server:

- Top, impossible to miss: `waiting_on_you` sessions, sorted longest-waiting first.
- Then `likely_stalled`, then `possibly_stuck` (clearly lower weight).
- Then `active`, low emphasis.
- Each row: human label (derive from repo/`cwd` — keep simple), status, time in that state.
- One action per row: **"Mark done"** — the ONLY way a session leaves the view. Never automatic.
- Empty state still says something true ("Nothing waiting — 3 active"), never blank.

## Out of scope — do NOT build

Chrome extension; SessionStart context-injection; idea/parking-lot capture; prioritizer; daily digest; session lineage / reopened-tab merging; the MCP/skill path; cross-restart resume; reading Claude Code transcripts; anything multi-machine/sync/teams.

(Note for future, do not build: `transcript_path` persists on disk and embeds `session_id`; a later opt-in feature could read past transcripts for retroactive discovery — explicit consent required since it reads full content. Design the event schema so this stays possible. Not v1.)

## README must state honestly

- "Claude finished and is waiting on you" → detected reliably.
- "Session went fully silent for a long time" → detected, confidence grows with time.
- "Stalled *inside* one long-running tool" → NOT reliably distinguishable from legitimately busy. Platform limitation, not a shortcut. Say so plainly.
- Positioning line: "Claude Code's built-in Agent View tracks background (`--bg`) sessions. This tracks the normal interactive tabs Agent View doesn't — the ones you actually lose."

## Build order

1. Three hook scripts + settings wiring → `events.jsonl`. Verify each fires and writes the minimized line **in the VSCode extension**, two tabs in one window producing two distinct `session_id` streams.
2. Server: read the file, derive per-session state with the confidence tiers.
3. Dashboard: prioritized view + "Mark done".
4. Stop. Everything under "Out of scope" stays unbuilt.

## Rules recap

Absolute paths in hooks · local file append only, no network, minimized fields · `session_id` is the key, never `cwd` · file is truth, server tolerates being offline and catches up on re-read · no auto-completion, ever.

Build exactly this. The deferred items are deferred deliberately so the core is trustworthy first. If something is genuinely ambiguous, ask before expanding scope — do not resolve ambiguity by building more.
