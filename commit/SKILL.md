---
name: commit
description: Commit only the changes made in the current session, leaving other agents' and the user's uncommitted work untouched, even in the same files. Flags suspicious files, runs the repo's checks, and writes a meaningful message.
argument-hint: "[optional context: which part of the session's work to commit, or how to split it]"
allowed-tools: Bash(git *), Bash(mktemp *), Bash(rm *), Read, Write, Grep, Glob, AskUserQuestion
---

# Session commit

Commit the work this session did, and nothing else.
Other agents and the user may have uncommitted changes in the same checkout, staged or not, even in the same files.
Those must never end up in this commit, and nothing in the working tree or in other people's staged changes may be modified.

User-provided context: $ARGUMENTS

## Dynamic context

These run in the session's working directory.
If the commit is for a different repo, run them there yourself.

- Status: !`git status --short 2>&1`
- Recent commits: !`git log --oneline -10 2>&1`

## Workflow

### Step 1 - List what this session changed

From this conversation, list every file this session changed in this repo: with Write, Edit and MultiEdit, through Bash (`sed`, scripts, `git mv`, `rm`, generators, formatters), and through subagents it started.
For each file, note what the session changed in it.

If part of the session is no longer in your context (for example after compaction) and you cannot tell which changes are yours, say so and ask the user with `AskUserQuestion` instead of guessing.

Every other entry in `git status` is someone else's.
Leave those alone: do not stage, stash, revert or commit them, and do not mention them unless they block this commit.

If the session changed nothing in this repo, say so and stop.

### Step 2 - Separate your hunks from everyone else's

For each session file, run `git diff --no-ext-diff --no-color HEAD -- <file>` (for a file that is not in HEAD, it is new) and sort it into one of these:

- **Whole**: every hunk is the session's.
  The session created the file, or the file had no other uncommitted changes.
- **Partial**: some hunks are someone else's.
  Write a patch that holds only the session's hunks, copied unchanged from the diff output, with the `---`/`+++` header and fixed hunk line counts.
- **Tangled**: a single hunk mixes the session's lines with someone else's, so they cannot be split cleanly.
  Ask the user whether to commit the whole file anyway, which takes the other changes with it, or leave it out.

### Step 3 - Check for suspicious files

A session file is suspicious if its name matches any of:

- **Databases**: `*.db`, `*.sqlite`, `*.sqlite3`
- **Secrets/keys**: `*.pem`, `*.key`, `*.env`, `*.secret`, `credentials*`, `*token*`, `*.p12`, `*.pfx`, `*.jks`
- **Caches/build artifacts**: `__pycache__/`, `.cache/`, `*.pyc`, `node_modules/`, `*.egg-info/`, `dist/`, `build/`
- **OS files**: `.DS_Store`, `Thumbs.db`
- **Archives/binaries**: `*.zip`, `*.tar.gz`, `*.jar`, `*.war`

Only session files count.
For each suspicious one, ask with `AskUserQuestion`: add to `.gitignore`, leave out of this commit, delete, or commit anyway.

### Step 4 - Choose the commits

By default, everything the session changed goes into one commit.
If the user-provided context above or the conversation names a subset, or asks for incremental or split commits, group the session's files and hunks into logical commits and run Step 6 once per group.

### Step 5 - Write the message and approve

- **Title**: short imperative sentence, under 72 characters.
- **Body**: 1-3 lines on the why, not the what.
- Match the style of the recent commits above.
- Follow the user's commit message rules from their instructions, including any rule about attribution trailers such as `Co-Authored-By`.

Use `AskUserQuestion` to show, for each planned commit, the files (marking partial ones and any whole file the user allowed despite other changes), the diff stat from Step 6, and the message.
Ask to **approve**, **edit the message**, or **cancel**.

Skip the approval only if the user said in this session that commits need no review (for example "commit incrementally, don't ask"), and nothing is tangled or suspicious.

### Step 6 - Commit through a private index

The shared index may hold other people's staged changes, so build the commit in a private index that starts from HEAD.
Run these steps in one Bash call, so the index path stays the same:

```bash
idx=$(mktemp -t session-commit)
staged=$(git diff --cached --name-only)          # paths other people have staged
GIT_INDEX_FILE=$idx git read-tree HEAD
GIT_INDEX_FILE=$idx git add -- <whole files>      # also stages deletions of whole files
GIT_INDEX_FILE=$idx git apply --cached <patch>    # once per partial patch
GIT_INDEX_FILE=$idx git diff --cached --no-ext-diff --stat
```

Check the stat: it must list exactly the planned files, with the planned line counts.
If not, delete the index, fix the patch, and start again.

Then commit with the same index and the message in a file:

```bash
GIT_INDEX_FILE=$idx git commit -F <message-file>
```

When the user asks to amend, use `git commit --amend` with the same private index; the private index starts from HEAD, so the amended commit keeps everything it already had.
`git commit` refuses to move HEAD if another commit landed in the meantime.
If that happens, start Step 6 again from a fresh index on the new HEAD.

After a successful commit, sync the shared index for the committed paths that nobody else had staged, so `git status` does not show them as staged changes:

```bash
git reset -q -- <committed paths that are not in $staged>
rm -f "$idx" <patch files> <message-file>
```

This only changes index entries, never the working tree.
Then run `git log --oneline -3` and `git status --short` to confirm the commit holds the session's work and every other change is still where it was.

## Rules

- Never `git add` to the shared index, and never use `git stash`, `git checkout -- <file>`, `git restore` or a `git reset` that touches other people's paths.
- Never commit, revert or clean up changes that are not from this session.
- If a pre-commit hook fails, fix the cause and commit again; never skip hooks with `--no-verify`.
- Do not push unless the user explicitly asks.
  Before pushing, show `git log --oneline @{u}..HEAD`; if it holds commits this session did not create, ask before pushing them.
