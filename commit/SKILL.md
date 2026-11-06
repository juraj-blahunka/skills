---
name: commit
description: Analyze changes, stage files, and create a meaningful commit. Flags suspicious files before committing.
argument-hint: "[optional context about the change]"
allowed-tools: Bash(git *), Read, Grep, Glob, AskUserQuestion
---

# Smart Commit

You are performing a smart commit workflow. Analyze the working tree, flag suspicious files, stage appropriate changes, and create a well-crafted commit.

User-provided context: $ARGUMENTS

## Dynamic context

```
! git status
```

```
! git diff --stat
```

```
! git log --oneline -5
```

## Workflow

### Step 1 — Analyze changeset

Review the injected git status and diff stat above to understand all changes: staged, unstaged, and untracked files. Identify what was added, modified, and deleted.

### Step 2 — Detect suspicious files

Scan ALL changed and untracked files against these patterns. A file is suspicious if its name matches any of:

- **Databases**: `*.db`, `*.sqlite`, `*.sqlite3`
- **Secrets/keys**: `*.pem`, `*.key`, `*.env`, `*.secret`, `credentials*`, `*token*`, `*.p12`, `*.pfx`, `*.jks`
- **Caches/build artifacts**: `__pycache__/`, `.cache/`, `*.pyc`, `node_modules/`, `*.egg-info/`, `dist/`, `build/`
- **OS files**: `.DS_Store`, `Thumbs.db`
- **Archives/binaries**: `*.zip`, `*.tar.gz`, `*.jar`, `*.war`

### Step 3 — Handle suspicious files

If ANY suspicious files are found among the changed/untracked files, you MUST stop and use `AskUserQuestion` to ask the user what to do. List each suspicious file with these options:

- **Add to .gitignore** — for files that should never be tracked
- **Keep unstaged** — leave as-is, just don't include in this commit
- **Delete** — remove the file from disk
- **Stage anyway** — user explicitly wants it committed

Then execute the user's choice:
- If "add to .gitignore": append the pattern to `.gitignore` and run `git add .gitignore`
- If "keep unstaged": do nothing with that file
- If "delete": remove the file with `rm`
- If "stage anyway": include it in the staging step

### Step 4 — Stage appropriate files

Run `git add` for all clean, relevant files. Stage files individually by name — do NOT use `git add -A` or `git add .`.

If the user provided `$ARGUMENTS`, use that context to understand which files are relevant to this commit. If no context was provided, stage all non-suspicious changed files.

### Step 5 — Generate commit message

Run `git diff --cached` to see exactly what will be committed. Then craft a commit message:

- **Title**: short imperative sentence, under 72 characters (e.g. "Add user authentication middleware")
- **Body**: 1-3 lines explaining the *why*, not the *what*
- Match the style of recent commits shown in the git log above

### Step 6 — Present commit for approval

Use `AskUserQuestion` to show the user:
1. The list of staged files
2. The proposed commit message

Ask them to **approve**, **edit the message**, or **cancel**.

If the user wants to edit, use their revised message. If cancelled, unstage all files with `git reset HEAD` and stop.

### Step 7 — Commit

Execute `git commit` using a HEREDOC for the message:

```bash
git commit -m "$(cat <<'EOF'
<title>

<body>
EOF
)"
```

Run `git status` after to confirm the commit succeeded.

## Important rules

- NEVER use `git add -A` or `git add .`
- NEVER skip pre-commit hooks (`--no-verify`)
- NEVER amend a previous commit — always create a new one
- If a pre-commit hook fails, fix the issue, re-stage, and create a NEW commit
- Do NOT push to remote unless the user explicitly asks
