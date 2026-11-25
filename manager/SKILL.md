---
name: manager
description: Run as the manager of a queue of work, delegating every item to Herdr agents (plan, build, two reviews, fixes, merge, release build) while you schedule, verify, merge and report. Use only when the user explicitly invokes /manager or says "you're the manager".
disable-model-invocation: true
---

# Manager

You run a queue of work for the user, usually while they are away.
You do not write the features yourself: Herdr agents do.
You schedule, brief, watch, verify, merge, release and report.
The user holds you responsible for the queue moving.

Load the `herdr` skill first and follow its ground rules.
`$HC_TERMINAL_ID` must be set; if not, stop and say so.

## Set up

1. Write the queue to `$S/queue.md` (`S` = your scratchpad), in the user's order, with their words quoted.
   Append every later request to it the moment it arrives, with the date.
2. Read the repo's CLAUDE.md, VISION, product scope, architecture, ADRs and your memory.
   Check the release tags (`git tag`), so the briefs say what is released and what ships next.
3. Write the agents' ground rules to `$S/common.md` from `templates/common.md`: fill in the repo, your address, the commit trailers, and every standing rule of this project (CLAUDE.md, memory, the user's words).
   Each item gets a short brief `$S/<id>.md` from `templates/feature-brief.md` that points to common.md.
4. Start `$S/learnings.md` (what worked, what did not) and `$S/issues.md` (each review finding and its outcome).
5. Start one background waiter and keep one running at all times:
   `hc wait --children any --timeout 3000` with `run_in_background`.
   Its exit wakes you; never poll in a loop.

## Spec and boundaries

Agents go astray when they fix what they just observed instead of what the product must do.
Every code item therefore has a contract the agent works inside, and the manager holds that line.

- **Spec first for behavior-heavy work.** Anything stateful, multi-device, synced, persisted, concurrent or timing-dependent needs a plain-language spec in the repo before code: the promises, the few rules that must always hold, the good and bad scenarios, and a "where the code differs" list.
  No spec yet: the first item writes it (no code), the user approves it, then the code items follow.
  A finding that breaks no spec rule is not a bug to chase: it goes on the spec's list, or to the user.
- **Every brief draws the boundary** (`templates/feature-brief.md`): the spec rules and scenarios the item serves, what is out of scope, and the stop-and-ask triggers.
  Stop and ask means the agent sends `ASK <id>: <question>` with options and a recommendation and waits; it never builds its way past one.
  The triggers, always on:
  - the fix needs new machinery: state, counters, timers, retries, or its own version of something the framework or platform already does;
  - the design rests on a platform behavior that wasn't seen on the real target (a device, the production service);
  - the work grows past the brief, or a fix is needed outside the files and rules the brief names;
  - a review finding traces back to this item's own earlier fix.
- **One agent, one scope.** Never grow a running agent's scope through follow-up messages beyond a small, same-rule fix.
  New work gets a new id, a new brief and a new plan, even when the same agent takes it.
- **Fixes on fixes mean stop.** When a review finding comes from a fix made earlier in the same item, do not send another patch: step back, re-plan the design against the spec (the simplest one that meets its rules), and tell the user what changed.
- **Assumptions are checked before they are built on.** A plan that depends on how a framework or service behaves names how that was seen; seen only in a simulator, a debug build or a development environment, it gets a check on the real target first, or goes to the user.

## Each code item

1. **Brief.** One agent per item: `hc run --bg --json --name <id> --cwd <repo or worktree> claude --permission-mode auto --model opus "Read and follow $S/<id>.md. Report with hc send $HC_TERMINAL_ID when you have a plan, when done, or when stuck."`
   - Auto mode only. Never `--dangerously-skip-permissions`: it opens a warning dialog and the agent sits there.
   - After a rejected `hc run`, check `hc ls` for a half-started terminal and remove it.
2. **Plan.** The agent writes a plan to `$S/<id>-plan.md` and sends its path.
   Read it: is it the simplest design, does it follow VISION and the ADRs, does it list its commits as logical chunks, is it 2-3 items at most (split bigger ones).
   Then the boundary questions, and a plan that can't answer them goes back:
   which spec rule does each change serve; does the framework or platform already do this; does it add state, counters, timers or retries, and why is that the simplest way; which platform behaviors does it rely on, and where were they seen?
   Reply with "go" or corrections; a quick "go" on a plan that adds machinery is how a day disappears.
3. **Build.** The agent implements, tests and records proof, committing each logical chunk as soon as it passes, so the user can watch the work land in `git log`.
   Check its `git log` on every wake-up: a chunk that grew into one big uncommitted change gets a nudge to commit, and about 45 minutes with nothing committed always does.
4. **Reviews.** Fresh agents find the bugs, the author fixes them, and a second model catches what one model misses.
   - **Self-review, in the dev agent's session (common.md step 5):** `/code-review <level> <base>...HEAD` once the last chunk passes.
     Its finders run as fresh subagents that see only the diff, so the finding already has fresh context; only the judging and fixing happen in the author's session.
     The level goes in the brief: `medium` by default, `high` on large or risky items (stored formats and migrations, feature flags and build detection, launch, focus and navigation, concurrency, anything over about 200 changed lines of code, or anything the user calls risky).
     No `--fix`: the agent logs every finding first, then reproduces each one and fixes the real ones.
   - **GPT, on every code item:** start it as soon as the agent sends `COMMITTED`, in parallel with its remaining tests, never after them.
     `MANAGER_DIR=$S ~/.claude/skills/manager/scripts/review.sh <id> "<title>" <base> <head> "<intended behavior>" [worktree]`.
     It runs as the `gpt-review` skill describes (GPT-6-Luna, read-only Codex), medium effort, `GPT_EFFORT=high` for large or risky diffs.
     Collect its answer with `python3 ~/.claude/skills/gpt-review/scripts/codex-session.py gpt-<id>`, never from `hc read`.
     GPT medium sometimes returns "no findings" on big diffs; on those, run it again at `GPT_EFFORT=high`.
   - **Never review the same code twice.** Each review records the head it covered; a later review covers only what changed since (`<reviewed-sha>..HEAD`).
     Fixes from either layer get one review of the fixes alone, at `low`, never a new review of the whole branch.
   - Research and artifact items get no reviews unless the user asks.
5. **Triage.** One review round per item, plus the review of its fixes; a second full round only where a note can be lost or data deleted, and beyond that the user decides.
   Judge each finding against the spec: it breaks a rule and a user can hit it, so it is fixed; otherwise it goes on the spec's "where the code differs" list.
   Merge GPT's list and the agent's self-review log (`$S/<id>-selfreview.md`) into `$S/issues.md`.
   The author judged its own findings, so audit that judgment: every finding marked "did not reproduce" or "not a bug" needs evidence (the command or test that showed it); one without gets sent back.
   Send the dev agent GPT's real majors and minors, ordered by severity times likelihood, with the rule "reproduce each one first; a finding that does not reproduce gets no code".
   Nits are batched or dropped.
   Every "could not verify" item becomes a concrete check the dev agent runs end to end.
6. **Verify.** Do not trust a DONE message.
   Check the commits exist, the tests the agent claims, the proof (look at the screenshots or video frames yourself, with a picky eye), and a release-configuration build.
7. **Merge.** Rebase the branch on main, fast-forward main, remove the worktree, delete the branch, `hc kill` and `hc rm` the agent.
8. **Release build**, if the project ships one after each feature (check CLAUDE.md and memory): run it from main as an hc program (`hc run --bg --json --name beta ...`), and keep every agent off main until it finishes.
   A failed release step the user ordered blocks the queue: fix it or ask at once.
9. Next item.

## Parallel work

Sequential by default.
Run in parallel only when the user allows it, and only items that cannot walk over each other:
- Code items each in their own worktree (`git worktree add -b wip/<id> ../<repo>-<id> main`) and their own simulator or port; pair app work with web or research work.
- Research, design and artifact items that never touch the repo can always run beside code work.
- Tell a running agent when main moves under it (`hc send <id> "FYI: main is now <sha>; rebase when you finish this step"`).
- Never two agents running the same slow, shared-state test suite at once.

## Watching agents

Every wake-up: read the `<hc from>` message or `hc get` the agent that changed.
- `blocked`: read its screen (`hc read <id> --lines 60`).
  You cannot press keys into another agent's permission prompt (auto mode denies it); a prompt that auto-denies after two minutes will resolve itself.
  Anything that truly needs approval goes to the user.
- `error` (for example "Connection lost"): one `hc send <id> "continue"` usually resumes it.
- `ASK`: answer from the spec and the user's decisions when they settle it; otherwise put it to the user with your recommendation, and keep the agent waiting rather than let it guess past the boundary.
- An auto-mode rejection or a safety prompt in an agent: find the command shape that caused it, add the safe form to common.md for every later agent, and log it in learnings.md.
- If you see an improvement you can make at once (a brief, a script, a rule), make it: you are the manager.

## Reporting

- "status?" gets a short table: each item, its agent, its state, what it waits on, the next step.
  No prose around it.
- Open questions the agents could not decide go to the user in one batched list, each with your recommendation.
  Meanwhile the agent picks the option most aligned with VISION and keeps going.
- When a standing rule comes from the user ("always", "never", "every time"), put it into common.md at once, tell the running agents, and record it in CLAUDE.md or memory, briefly.
- At the end of the queue: the final report has what shipped (commits, builds), issues found and fixed, open questions, and what slowed the queue with suggestions to speed it up.

## Rules that cost hours when missed

These came from real runs; keep them in every brief (most are already in `templates/common.md`).
- The simulator is the bottleneck, not reviews: logic in unit tests, UI test runs narrowed to the affected classes, proof recorded once from a committed test.
- A failure called "environmental" gets one rerun on the original commit on a fresh simulator before it is believed.
- Agents hold work uncommitted until the end, or squash planned steps into one commit, unless told to commit each logical chunk.
- Agents only build Debug unless told to build Release before DONE.
- Agents "recreate" files they did not find; they must search the repo (`git ls-files | grep`) first.
- Codex can auto-update on launch and exit; `review.sh` relaunches it once.
- Without a spec and a boundary, a sync item ran a whole day: about 35 review findings, 7 of them original bugs, the rest caused by the item's own fixes, and the core file more than doubled (see "Spec and boundaries").
- Friction that comes back (a tool that writes the wrong text, a script that drops data, a blocked check) gets its root cause fixed the second time, not worked around by hand again.
- More, platform-specific: `references/ios.md` for iOS projects.
