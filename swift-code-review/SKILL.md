---
name: swift-code-review
description: Run a staff-engineer adversarial review of the non-UI business logic in a Swift codebase. Launches parallel Explore agents across the codebase, synthesizes findings by severity, writes a prioritized plan, and optionally implements the fixes.
argument-hint: "[optional: path glob or focus area, e.g. 'Persistence/' or 'src/billing/']"
allowed-tools: Bash, Read, Write, Edit, Agent, AskUserQuestion
---

# Adversarial Code Review - Staff Engineer Mode

You are acting as an adversarial staff engineer conducting a deep review of the non-UI business logic in this codebase.
Your goal is to surface real, actionable issues, not style nits.

User-provided focus area (optional): $ARGUMENTS

## Workflow

### Phase 1 - Map the codebase

List the source files, excluding build output, generated code, vendored dependencies, UI layers, UI tests and assets.
Identify the primary language(s) and frameworks.

Group the non-UI files into 3 logical clusters of roughly equal weight for parallel analysis.
Derive the clusters from the actual architecture, for example:
1. **Core domain / state** - main loop, state machines, rules, models, orchestration
2. **Persistence / data** - database access, caches, serialization, migrations, configuration
3. **Integration / security / utilities** - networking, auth, identity, licensing, notifications, OS integration, helpers

Use any `$ARGUMENTS` to narrow focus (e.g. only review `Persistence/`).
If no arguments are given, review everything.

### Phase 2 - Parallel deep reads (3 Explore agents)

Launch all 3 agents in a **single message** (parallel).
Each agent must:
- Read every file in its cluster **fully**
- Read any test files that exercise those files
- Report per-file findings under these headings:
  - **Core responsibility** (1 sentence)
  - **Concurrency hazards** - isolation violations, untracked background tasks, fire-and-forget side effects, missing awaits, data races
  - **Logic bugs** - wrong calculations, incorrect state transitions, silent wrong-path returns, off-by-one
  - **Error handling gaps** - swallowed errors, force-unwraps, silent fallbacks that mask failures
  - **Security issues** - token/key handling, permission gaps, stale identifiers, injection vectors
  - **Test gaps** - scenarios that should be tested but aren't

Instruct each agent: "Be adversarial and specific. Only report real problems, not style nits. Include file path and approximate line number for each finding."

### Phase 3 - Synthesize findings

After all 3 agents return, merge and deduplicate their findings.
Verify each finding against the code before keeping it.
Classify each issue:

- **CRITICAL** - data loss, security hole, crash, concurrency violation that breaks correctness in tests or production
- **HIGH** - silent failures, incorrect logic that produces wrong results, design flaws with user-visible impact
- **MEDIUM** - missing validation, fragile code that's one refactor away from breaking, error handling gaps
- **LOW** - minor inconsistencies, misleading comments, cosmetic robustness improvements

### Phase 4 - Write the plan

Write findings to `~/.claude/plans/swift-code-review-<IDENTIFIER>.md` using this structure:

```
# Adversarial Review - <Date>

## CRITICAL
### C1 · <short title>
**File:** `path/to/file` line ~N
<description of the problem>
**Fix:** <concrete fix>

### C2 · ...

## HIGH
### H1 · ...

## MEDIUM
### M1 · ...

## LOW | table
| Issue | File | Note |
...

## Test Coverage Gaps
| What | Where |
...

## Recommended Remediation Order
1. C1, C2, ... - reason
2. ...
```

### Phase 5 - Present findings

After writing the plan, summarise the findings to the user:
- Total count per severity tier
- Top 3 most impactful issues (1 sentence each)
- Path to the full plan file

Then ask the user what they want to do next:

```
AskUserQuestion:
  "N issues found (X critical, Y high, Z medium). What would you like to do?"
  Options:
    - "Implement all fixes (start with CRITICAL)"
    - "Implement CRITICAL only"
    - "Review the plan first, I'll tell you what to fix"
    - "Nothing - findings only"
```

### Phase 6 - Implement (if requested)

If the user wants fixes implemented, work through them in remediation order.
For each fix:
1. Read the target file(s) before editing
2. Make the minimal correct change
3. Run the test suite after each severity tier completes
4. If tests fail, diagnose and fix before continuing

After all fixes are applied, show a summary of the changes.

## Review principles

**Concurrency**
- Background work started in a constructor or without a stored handle is a red flag
- Swallowed errors on writes (e.g. `try? await db.write {}` in Swift) are a red flag
- Fire-and-forget side effects must be justified or fixed
- Main-thread or actor-isolated state accessed from non-isolated contexts

**State machines**
- Can the system get into an unrepresentable state?
- Are resets complete (all fields, not just some)?
- Are external identifiers (PIDs, file handles, session IDs) re-validated before reuse?

**Error visibility**
- Every swallowed error should be questioned: is it truly ignorable?
- Silent early returns from fallible functions break caller contracts
- Configuration and deserialization failures should be logged

**Security**
- Identity or device binding: does a fallback weaken the guarantee?
- File permissions: are sensitive files written with restrictive modes?
- Destructive actions: are stored identifiers re-validated before acting on them?

**Data integrity**
- Multi-step writes: does a later step run even when an earlier one was a no-op or failed?
- Are batch and aggregation jobs idempotent?
- Are finalization steps awaited before state is reset?

**Test quality**
- Tests that pass vacuously (a conditional branch that is never taken) mask bugs
- Environment-sensitive tests should guard against the degenerate case
- Fire-and-forget work in production code causes test isolation bugs (mutations after teardown)
