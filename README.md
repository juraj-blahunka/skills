# skills

Personal agent skills.

Each skill lives in its own directory with a `SKILL.md`.
Install them into Claude Code with:

```sh
./install.sh
```

It removes every symlink in `~/.claude/skills` that points into this repo, then symlinks each skill directory there.
Re-run it after adding, renaming or deleting a skill.
Set `CLAUDE_SKILLS_DIR` to install somewhere else.

| Skill | Purpose |
|---|---|
| `commit` | Commit only the current session's changes, leaving other uncommitted work untouched |
| `gpt-review` | Independent GPT code review, returned verbatim |
| `herdr` | Work inside Herdr through `hc` and `herdr-app` |
| `swift-code-review` | Staff-engineer adversarial review of non-UI Swift business logic |
