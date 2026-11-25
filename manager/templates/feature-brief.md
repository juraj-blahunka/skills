# <id>: <title>

First read the ground rules: <$S>/common.md

Plan file: <$S>/<id>-plan.md
Report file: <$S>/<id>-report.md
Self-review file: <$S>/<id>-selfreview.md
Worktree: <path> (branch wip/<id>), or "main".
Review: `/code-review <medium, or high for a large or risky item> <base>...HEAD`, base <the commit of main this branch starts from>.

## What {{USER}} asked

<their words, quoted>

## Current state

<what changed on main since the queue started that this item touches: recent features, ADRs, tokens, flags>

## Spec

<the spec doc and the rules and scenarios this item serves, by name; "none needed" only for items with no stateful or multi-device behavior>

## Scope

- <what to build, with the decisions already made>
- <what is out of scope>
- Proof: <what the recording or screenshots must show>
- Time box: <about N hours>

## Boundary: stop and ask, don't build past it

Send `ASK <id>: <question, options, your recommendation>` and wait when:
- the work needs new machinery (state, counters, timers, retries, or a home-made version of what the framework already does);
- the design rests on platform behavior not seen on the real target;
- the work grows past this brief or needs files and rules it doesn't name;
- a review finding traces back to a fix you made earlier in this item.
<item-specific triggers, if any>
