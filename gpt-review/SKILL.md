---
name: gpt-review
description: Launch an independent GPT-6-Luna code review and return it verbatim. Use only when the user explicitly invokes /gpt-review.
disable-model-invocation: true
triggers: [user, model]
---

# GPT Review

Always use **GPT-6-Luna** through the Codex TUI, orchestrated by Herdr (`hc`).
Default to **medium reasoning**.
Use another effort only when the user explicitly asks, and only one that `codex debug models` lists for `gpt-6-luna`.
Never use another model.
The account is on the free plan: never pass a service tier (`service_tier`, fast or priority).

## Run

Load the `herdr` skill and follow its ground rules.
`$HC_TERMINAL_ID` must be set; if it is not, stop and report that hc is unavailable.
Reuse the current environment, including uncommitted work: launch in the current working tree, never a fresh clone or worktree.

Before spawning, confirm the live catalog lists `gpt-6-luna` with the chosen effort:

```bash
codex debug models | python3 -c 'import json,sys; m=next((m for m in json.load(sys.stdin)["models"] if m["slug"]=="gpt-6-luna"),None); print(m and [e["effort"] for e in m["supported_reasoning_levels"]])'
```

Spawn an interactive, read-only Codex and wait until it is ready:

```bash
hc run --bg --json --name gpt-review --cwd "$PWD" \
  codex --no-alt-screen -m gpt-6-luna -c model_reasoning_effort=medium -s read-only -a never
hc wait gpt-review --timeout 60      # expect status idle, turn 0
```

- `-s read-only -a never` keeps the reviewer from changing files and from blocking on approvals.
- Do not pass the brief as Codex's argv prompt: hc cannot see that as a launch task, so `hc wait` returns at startup idle before the review starts.
- Never use `codex exec` or `codex review`; the reviewer must stay watchable and available for a follow-up turn.
- A Codex startup warning about running without the shared background server (caused by `-c`) is expected.

Write the brief (see below) to a file in the scratchpad and send it as one message:

```bash
hc send --wait --timeout 110 gpt-review "$(cat "$BRIEF")"
```

Then confirm what actually runs, from Codex's own session log:

```bash
python3 ~/.claude/skills/gpt-review/scripts/codex-session.py gpt-review
```

Every entry in `turns` must show `model: gpt-6-luna`, the chosen `effort`, and `sandbox: read-only`.
If any check fails, stop, clean up, and report the blocker.
Never silently fall back to another model, effort, harness, or plan.

## Review brief

Give neutral context: scope, paths, intended behavior, and diff/base revision.
Ask for a thorough senior-developer review, including related code and tests, without steering toward suspected bugs, solutions, or verdicts.
Review only; do not change files.
Request a concise plain-English report of serious or critical issues, fixes, and production merge readiness.
Distinguish verified findings from uncertainty and identify validation gaps.
The message arrives wrapped in `<hc from="...">` tags; tell the reviewer to give the whole report as its final answer and not to reply through hc (its sandbox is read-only).

Include this sentence in the brief, word for word: "During your final answer, Rate each issue you find from 1 to 10 on how often it would happen, and 1-10 on how bad it would be"

## Result

`send --wait` returns when the turn ends or its timeout passes.
Until the review is done, keep waiting with hc, never sleep or poll:

```bash
hc wait gpt-review --timeout 110
```

- `reason: timeout` is a check-in; wait again.
- `status: blocked` or `error`: `hc read gpt-review --lines 80`, and report what it shows instead of pushing past it.
  Free-plan usage or rate limits show up here; they are blockers, not a reason to switch models.

When hc reports `status: done`, run `codex-session.py gpt-review` again.
The review completed only when `last_turn_completed` is `true`, `final_answer` is non-empty, and every turn still shows `gpt-6-luna` at the chosen effort.
Idle status, timeouts, aborted turns, `errors`, and queued retries are not completion.
Report blockers rather than presenting partial output as a finished review.

Return `final_answer`, the completed reviewer's full final response, verbatim.
Take it from the session log, never from `hc read`: the TUI renders Markdown and rewraps lines, so its screen is not verbatim.
Then clean up: `hc kill gpt-review && hc rm gpt-review`, unless the user wants a follow-up turn with the same reviewer.
