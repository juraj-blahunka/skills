---
name: promote-skill
description: Promote a skill that lives inside the current project (for example `.claude/skills/<name>/`) into this personal skills repo, so it is available in every project. Reviews every file of the skill for personal information (names, emails, usernames, home paths, hosts, tokens) and project-specific information (repo names, paths, schemes, bundle IDs, internal services, team conventions), generalizes or removes what does not belong, moves the skill, updates the README and installs it. Use when asked to promote, move, extract, globalize or share a local or project skill.
argument-hint: "[skill name or path; default: ask which local skill]"
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, AskUserQuestion
---

# Promote skill

Move a skill out of the current project into the personal skills repo, generalized so it works in any project and leaks nothing private.

Skill to promote: $ARGUMENTS

## Step 1 - Find the two repos

**Skills repo**: the git repo this skill itself lives in.
Resolve this skill's base directory through its symlink, then take the repo root:

```bash
skills_repo=$(cd "<base directory of this skill>" && cd "$(pwd -P)" && git rev-parse --show-toplevel)
```

If that does not resolve to a git repo with an `install.sh` and a `README.md`, stop and ask the user where the skills repo is.

**Project**: the current working directory's git root (`git rev-parse --show-toplevel`).
If the project is the skills repo itself, stop: there is nothing to promote.

## Step 2 - Pick the skill

Local skills live in the project under `.claude/skills/*/SKILL.md`, and sometimes `.agents/skills/*/SKILL.md` or `skills/*/SKILL.md`.
Find them with:

```bash
find "$project" -path '*/node_modules' -prune -o -name SKILL.md -path '*skills/*' -print
```

Use the argument if it names one of them, by name or path.
Otherwise list what you found and ask with `AskUserQuestion`.
If the project has none, say so and stop.

Then check the destination:

- `$skills_repo/<name>/` must not exist.
  If it does, show both versions and ask whether to merge, rename, or stop.
- `${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}/<name>` must not be taken by something outside the skills repo; `install.sh` would skip it.

## Step 3 - Read everything

Read every file in the skill directory in full: `SKILL.md`, scripts, references, templates, assets that are text.
Do not skim and do not skip files because they look boilerplate.
List binary files and say what they are; flag any image or archive whose content you cannot check.

## Step 4 - Review for personal information

Build the list of identifiers to search for, from the environment rather than from memory:

```bash
whoami; id -un; hostname; echo "$HOME"
git config user.name; git config user.email
git -C "$project" remote -v
```

Search the skill for each of them, case-insensitively, and also for:

- Names, emails, phone numbers, usernames and handles of the user or anyone else.
- Absolute home paths (`/Users/<user>/`, `/home/<user>/`, `C:\Users\<user>\`).
- Hostnames, IPs, internal domains, VPN or SSH targets.
- Tokens, API keys, passwords, cookies, private keys, `.env` values, account or tenant IDs.
- Personal accounts and devices: simulator UDIDs, device names, Apple team IDs, signing identities.

A secret (token, key, password) is a stop: do not copy it anywhere.
Tell the user where it is and that it should be rotated if the project repo is shared or pushed.

## Step 5 - Review for project-specific information

Search for the project's own vocabulary: its directory and repo name, the remote's org, product and app names, and names that appear in the project's README or build files.
Then read the skill as if you were in a different repo, and flag every line that would be wrong or meaningless there:

- Paths into this project (`Sources/Foo/`, `apps/web/`, specific files).
- Build specifics: schemes, targets, bundle IDs, package names, ports, environment names, CI job names.
- Commands that only exist here (`make deploy-staging`, `./scripts/release.sh`).
- Internal services, dashboards, tickets, channels, people to ping.
- Team conventions stated as universal rules.

## Step 6 - Decide what to do with each finding

For each finding, pick one:

1. **Generalize**: replace the specific with how to discover it in any repo.
   "Run `xcodebuild -scheme Acme`" becomes "find the scheme with `xcodebuild -list`".
2. **Externalize**: when the project-specific part is the valuable part (a build recipe, a list of services), make the skill read it from the repo's `AGENTS.md`, or `CLAUDE.md` if there is no `AGENTS.md`, under a `## <Skill name>` section, and move the specifics into that section in the project.
   The `verify` skill and its `## Verify` recipe follow this pattern.
3. **Remove**: when it only served this project and generalizing adds nothing.
4. **Keep**: only when it is genuinely universal, such as a public tool's name.

If the skill does not survive generalization (it is mostly project specifics), say so and recommend keeping it local instead.

## Step 7 - Show the plan and get approval

Present, with `AskUserQuestion` where there is a real choice:

- Every finding: file, line, the text, and the chosen treatment.
- The full diff of the generalized skill against the original.
- Any section that would be added to the project's `AGENTS.md` or `CLAUDE.md`.
- Whether the original is removed from the project.
  Ask explicitly when the skill is tracked in git there: teammates may rely on it, and keeping it until they switch can be the better choice.

Change nothing until the user approves.

## Step 8 - Move it

1. Copy the skill directory to `$skills_repo/<name>/` with permissions intact (`cp -Rp`), then apply the approved edits there.
   Never edit the project's copy in place first.
2. Make sure the frontmatter `name` matches the directory name, and the `description` says what the skill does and when to use it, with nothing project-specific.
3. Re-run the searches from steps 4 and 5 against the new copy.
   Every hit must be one the user approved keeping.
4. Add a row to the skills table in `$skills_repo/README.md`, keeping the table's existing order and style.
5. Add the `## <Skill name>` section to the project's instructions file, if approved.
6. Remove the original from the project, if approved: `git rm -r` when tracked, `rm -r` when not.
   Then search the project for references to the old path or name (`CLAUDE.md`, `AGENTS.md`, `.claude/settings*.json`, docs, scripts) and update them.
7. Run `$skills_repo/install.sh`, and confirm the new skill is linked in the output.

## Step 9 - Report

Tell the user:

- Where the skill now lives, and that it is installed.
- What was generalized, externalized and removed, briefly.
- What changed in the project: removed files, edited instructions, updated references.
- Any secret found, and the advice to rotate it.

Do not commit in either repo unless the user asks.
When they do, make one commit per repo: the addition in the skills repo, the removal and any instructions changes in the project.
