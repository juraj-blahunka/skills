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
| `create-image` | Generate or edit an image through OpenRouter, FLUX 3 Klein at about 2 MP by default |
| `gpt-review` | Independent GPT code review, returned verbatim |
| `herdr` | Work inside Herdr through `hc` and `herdr-app` |
| `promote-skill` | Move a project-local skill here, stripped of personal and project-specific details |
| `verify-changes` | Verify a change end to end through a Haiku agent, using the repo's own recipe |
| `swift-code-review` | Staff-engineer adversarial review of non-UI Swift business logic |
