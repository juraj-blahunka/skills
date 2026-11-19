---
name: create-image
description: Generate or edit an image through OpenRouter. Defaults to FLUX 3 Klein at about 2 MP, one image. Use when the user asks to create, generate, render or edit an image and no project-specific image skill covers it.
---

# Create image

Run `uv run <this skill's dir>/scripts/or_image.py`; `--help` lists every flag.

## Defaults

Unless the user asks otherwise:

- Model `klein` (FLUX 3 Klein, about USD 0.01 an image).
  Use `gpt` for legible text or dense layouts, `nano` for edits that must keep a face identical; say the higher price first.
- Size `1.5K`, about 2 MP. One image.
  Fix a weak result with a targeted edit (`--ref` the result, describe the one change), not more variants.
- Always pass `--aspect`, picked from the destination: 9:16 story/Reel/phone, 4:5 feed post, 1:1 avatar/icon/logo, 16:9 thumbnail/slide/hero, 2:3 poster/cover, 21:9 banner; 1:1 when unclear.
  Leave it out for edits so the reference's shape is kept.
- Output to the path the user gives, else a fitting folder in the project, else the scratchpad (report the absolute path).

## Run

```bash
S=<this skill's dir>/scripts/or_image.py
uv run "$S" --prompt "..." --aspect 16:9 --out images --name hero
uv run "$S" --prompt "Keep everything, change only ..." --ref images/hero-...-1.png --out images
```

Each run saves the image plus a `.json` with the request and real cost; keep both.
Look at the result with Read before reporting it, and state the cost.

Prompts in English, one descriptive paragraph; no real brands, people or copyrighted characters.

## Setup

The key is `OPENROUTER_API_KEY` from the environment, else `.env` in this skill's dir (git-ignored).
