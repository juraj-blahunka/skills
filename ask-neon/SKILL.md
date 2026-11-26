---
name: ask-neon
description: Ask Gemini 4 Neon (google/gemini-4-neon on OpenRouter) a question, with a hard cost cap of USD 0.05 per call by default. Use when the user asks to "ask Neon", "ask Gemini", wants a second model's take, or wants a burst of creative options (names, taglines, ideas) from a different model.
---

# Ask Neon

Run `python3 <this skill's dir>/scripts/ask_neon.py`; `--help` lists every flag.

```bash
S=<this skill's dir>/scripts/ask_neon.py
python3 "$S" --prompt-file brief.md --save runs/names.json
python3 "$S" --prompt "..." --temperature 1.3
```

The answer goes to stdout; the cap, the token counts and the real cost go to stderr.

## Cost cap

- Default cap USD 0.05 per call; `--cap` changes it.
- Before the call, the script reads the model's live prices, estimates the prompt cost on the high side and sets `max_tokens` so prompt plus output (reasoning included) cannot exceed the cap.
- At USD 15 per million output tokens, 0.05 buys about 3,000 output tokens: enough for about 100 short one-line items or a page of prose.
  Ask for terse output (one line per item) so the answer fits; the script says when the answer was cut off at the cap.
- Reasoning tokens are billed as output and come out of the same budget as the answer.
- Neon always reasons.
  `--effort none` fails with HTTP 400 ("Reasoning is mandatory"), and a reasoning token budget is ignored.
  `minimal` (the default) is the lowest setting and still reasons: about 300 tokens for a five-word answer, and 1,348 of 1,853 output tokens on a 100-item list.
  At `--effort low`, the same 100-item list spent 2,228 of 3,229 tokens on reasoning and was cut off at item 74.
  Keep `minimal` for lists and brainstorming; use `low` or higher only for questions that need real thinking, with a higher `--cap` after telling the user the new figure.
- The script refuses a cap that leaves fewer than 600 output tokens, since reasoning alone can use about 300.
- Never raise the cap above USD 0.05 without the user's go.

## Prompting

- Write the prompt to a file when it is longer than a few lines, so it can be saved and reused.
- Give Neon full context: what the thing is, who it is for, the constraints, and the exact output format.
- `--temperature` 1.2-1.5 for wide brainstorming, default otherwise.

## Report

Show the user the answer (or a curated cut, plus the file with the full one) and always the real cost from the stderr line.
With `--save`, the JSON keeps the request, answer, usage and cost.

## Setup

The key is `OPENROUTER_API_KEY` from the environment, else `.env` in this skill's dir (git-ignored).
Never print the key.
