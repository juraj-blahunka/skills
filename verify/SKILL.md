---
name: verify
description: Verify a change end to end in any repo - build, lint, tests, then exercising it the way a user would (simulator, browser, CLI in a throwaway home) with screenshots checked closely and cleanup guaranteed. Runs the ladder in a background Haiku agent through Herdr, using the repo's own "## Verify" recipe, and drafts that recipe when the repo has none. Use when asked to verify, check, prove or confirm a change works, or before calling work done.
argument-hint: "[what to verify: a change, a feature, a commit range; default: this session's changes]"
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion
---

# Verify

Prove that a change works the way a user would experience it.
You plan and judge; a Haiku agent started through Herdr runs the ladder and reports back.

Focus from the user: $ARGUMENTS

## The ladder

Rungs run in this order, and the run stops at the first one that fails:

1. **Build**: the project compiles, including its tests.
2. **Lint**: the repo's linters and formatters in check mode.
3. **Test**: the full test suite.
4. **End to end**: the changed behaviour, exercised through the real product the way a user meets it:
   the app in a simulator, the page in a browser, the CLI in a throwaway home, the API with real requests.
5. **Look**: screenshots of every screen or page the change touches, at the sizes and appearances the recipe names.

A rung the project does not have (no linter, no UI) is skipped and reported as skipped, never as passed.

## Step 1 - Work out what to verify

Use the focus above if given.
Otherwise take this session's changes; if there are none, take the uncommitted changes, and if there are none, the last commit.
Write down, in plain words, the behaviours that changed and how a user would notice them.
That list drives rungs 4 and 5: they check the change itself, not only that the product still starts.

## Step 2 - Get the repo's recipe

Look for a `## Verify` section in the repo's `AGENTS.md`, or `CLAUDE.md` if there is no `AGENTS.md`.
If one exists, use it as written.

If none exists, draft one from what the repo already has: build files (`Package.swift`, `*.xcodeproj`/`*.xcworkspace`, `package.json`, `pyproject.toml`, `Makefile`), `scripts/`, CI workflows, the README, and existing testing notes.
Run each command you propose once yourself, so the recipe only holds commands that work.
Use this format, one line per rung, `none` where a rung does not apply:

```markdown
## Verify

How agents verify a change end to end; the `verify` skill runs it rung by rung and stops at the first failure.

- Build: `<command>`
- Lint: `<command>` | none
- Test: `<command>`
- End to end: <how to exercise a change for real: commands, the isolated home or data, the simulator or browser to use>
- Look: <what to screenshot, at which sizes and appearances> | none
- Isolation: <what must not leak: throwaway homes, test data, ports, simulators taken through simctlhouse>
- Cleanup: <what to remove afterwards, and the before and after check that proves nothing leaked>
```

Show the draft to the user with `AskUserQuestion` and add it to the instructions file only once they accept it.
That edit is the only change this skill makes to the repo.

## Step 3 - Start the Haiku agent

Make a results folder with `mktemp -d -t verify`, and start the agent from the repo root with the brief below:

```bash
hc run --bg --json --name verify-<repo> --cwd <repo root> claude --model haiku --permission-mode auto "<brief>"
```

- Put the whole brief in the `run` command; a `send` to an agent that is still starting can be lost.
- Pass no option between `--permission-mode auto` and the brief; `--add-dir` in particular swallows the brief as another directory.
- Write this session's own `$HC_TERMINAL_ID` into the brief, so the agent can report back.
- The repo root must be a folder the user already trusts.
  If the agent shows Claude Code's "trust this folder" prompt, kill it and ask the user to open Claude Code there once, or to accept the prompt in that terminal; never answer it for them.

The brief, filled in:

```text
You verify a change in this repo. Do not edit, commit, revert or delete anything in the repo; build output the
build writes itself is fine. Do not start other agents. Write all your files under <results folder>.

What changed and how a user would notice it:
<the list from step 1>

Recipe, from <AGENTS.md or CLAUDE.md>:
<the recipe>

Run the ladder in order: Build, Lint, Test, End to end, Look. Skip rungs the recipe marks none, and report them as
skipped. Stop at the first rung that fails.
- Save each rung's full output to <results folder>/<n>-<rung>.log.
- When a rung fails, run it once more. Report "fails every time" or "failed once, passed on retry (flaky)", with both logs.
- End to end: check each changed behaviour from the list above, one by one, and record what you ran, what you
  expected and what you saw.
- Simulators: always take them through the simctlhouse skill (simctlhouse run / acquire), never a simulator by name,
  and release them when done.
- Look: save every screenshot to <results folder>/screens/ with a name saying what it shows, size and appearance.
  Describe each one critically: misalignment, clipping, truncated text, wrong colors, overlap, empty or broken states.
- Isolation and cleanup: follow the recipe. Before end to end, record the counts the recipe's cleanup check names
  (for example the number of simulators); afterwards, clean up and record them again. A difference is a failure.
  Finally remove every temporary directory you created outside <results folder> (throwaway homes, built packages).
- Never wait with sleep for something a command can wait for itself.

Write <results folder>/report.md: one line per rung (passed / failed / flaky / skipped, duration, log path), then for
each changed behaviour what you checked and the result, then the screenshots with your notes, then the cleanup
counts before and after. Quote the exact failing lines.

When done, or stuck, run: hc send <$HC_TERMINAL_ID of this session> 'verify: <passed | failed at RUNG | stuck: reason>. Report: <results folder>/report.md'
```

## Step 4 - Wait, and handle a blocked agent

Wait with `hc wait --children any --timeout 110`, repeated until the agent's message arrives.
A timeout is only a check-in.
If the agent is `blocked` on a permission prompt, read its screen with `hc read`.
Ask the user about anything that writes outside the results folder, touches the network beyond the project's own needs, or deletes something.
Never approve a prompt by sending keys to the agent yourself.

## Step 5 - Check the report yourself

Treat the report as a claim, not a result:

- Open every failing log at the quoted lines, and confirm the failure is real and is what the report says.
- Look at every screenshot yourself, and be picky about pixels: alignment, spacing, clipping, truncation, contrast, dark mode, small sizes.
  Your own findings count even where the agent wrote "looks fine".
- Check that each changed behaviour from step 1 was really exercised, not only that the product started.
- Ask whether each passing check would have failed without the change.
  If it would not (a race too rare to hit, a path the old code handled too), say so: it shows nothing broke, not that the change works.
- Check the cleanup counts, and that no throwaway directory or process the agent made is left behind.

## Step 6 - Report and clean up

Tell the user, in this order:

1. The verdict: verified, or failed at which rung.
2. Per rung: result and duration, with flaky rungs called out as flaky.
3. Per changed behaviour: what was checked and what happened.
4. Visual findings, including yours.
5. Anything left behind, if cleanup did not hold.

Give paths in full: the report, failing logs and screenshots.
Then remove the agent with `hc kill verify-<repo> && hc rm verify-<repo>`, and keep the results folder for the user.

Do not fix anything as part of verifying.
If something failed, say what you would change and let the user decide.
