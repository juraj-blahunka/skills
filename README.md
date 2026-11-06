# skills

Personal agent skills.

Each skill lives in its own directory with a `SKILL.md`.
They are installed into Claude Code by symlinking each directory into `~/.claude/skills`:

```sh
ln -s "$PWD/<skill>" ~/.claude/skills/<skill>
```

| Skill | Purpose |
|---|---|
| `commit` | Analyze changes, stage files, and write a meaningful commit |
| `gpt-review` | Independent GPT code review, returned verbatim |
| `herdr` | Work inside Herdr through `hc` and `herdr-app` |
| `swift-code-review` | Staff-engineer adversarial review of non-UI Swift business logic |
