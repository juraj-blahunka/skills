---
name: focus
description: Do only the one task asked, with the smallest change that solves it; no other fixes, refactors or improvements. Use only when the user explicitly invokes /focus.
disable-model-invocation: true
---

# Focus

The user wants one thing done, and nothing else.

1. Restate the task in one line.
   If it's ambiguous, ask one question, then go.
2. Reproduce it first, the way the user experiences it (for a bug, end to end).
3. Make the smallest change that solves it.
   - Touch only the code the fix needs.
   - No refactors, renames, cleanups, comment rewrites or drive-by fixes, even for real problems you notice.
   - This overrides any standing rule to fix things along the way.
4. Verify only what the change can affect: the reproduction passes and the closest tests still pass.
5. Report in a few lines: the cause, the change, how it was verified.
   List anything else you noticed as one line each under "Not touched", and leave it.

When delegating, pass these rules to the agent word for word.
