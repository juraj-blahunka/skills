#!/usr/bin/env python3
"""Ask Gemini 4 Neon a question through OpenRouter, with a hard cost cap per call.

    python3 ask_neon.py --prompt "..."                 # answer on stdout, cost on stderr
    python3 ask_neon.py --prompt-file brief.md --save out/run.json
    echo "..." | python3 ask_neon.py --cap 0.02

The cap is enforced before the call: the script reads the model's live prices, estimates the prompt
cost on the high side, and sets max_tokens so that prompt plus output (reasoning included) cannot
cost more than --cap. The real cost comes from OpenRouter's usage field after the call.

The API key is OPENROUTER_API_KEY from the environment, else from the .env file next to this skill.
Stdlib only.
"""
import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://openrouter.ai/api/v1"
MODEL = "google/gemini-4-neon"
DEFAULT_CAP = 0.05
CHARS_PER_TOKEN = 3.0  # conservative: real English text is closer to 4, so the estimate runs high
OVERHEAD_TOKENS = 64  # chat template and role markers
MIN_OUTPUT_TOKENS = 600  # Neon spends about 300 reasoning tokens even on a one-line answer at minimal effort
SKILL_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = SKILL_DIR / ".env"


def fail(msg):
    sys.exit(f"error: {msg}")


def load_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key and ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        fail(f"OPENROUTER_API_KEY is not set; export it or put it in {ENV_FILE}")
    return key


def request(method, path, key=None, body=None, timeout=300):
    headers = {"Content-Type": "application/json", "X-OpenRouter-Title": "ask-neon"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")[:800]
        hints = {401: "check OPENROUTER_API_KEY", 402: "the account needs credits", 429: "rate limited, retry later"}
        fail(f"OpenRouter returned HTTP {e.code}: {text}" + (f" ({hints[e.code]})" if e.code in hints else ""))


def prices(model):
    for m in request("GET", "/models")["data"]:
        if m["id"] == model:
            p = m["pricing"]
            return float(p["prompt"]), float(p["completion"]), float(p.get("internal_reasoning") or p["completion"])
    fail(f"model {model} not found on OpenRouter")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompt", help="the question; else --prompt-file, else stdin")
    ap.add_argument("--prompt-file", help="read the prompt from this file")
    ap.add_argument("--system", help="optional system message")
    ap.add_argument("--cap", type=float, default=DEFAULT_CAP, help=f"max USD for this call (default {DEFAULT_CAP})")
    ap.add_argument("--effort", default="minimal", choices=["none", "minimal", "low", "medium", "high"],
                    help="reasoning effort (default minimal); reasoning tokens are billed as output and count toward "
                         "the cap. Neon cannot turn reasoning off: 'none' is passed through and Neon rejects it")
    ap.add_argument("--temperature", type=float, help="sampling temperature, for example 1.3 for wild brainstorming")
    ap.add_argument("--model", default=MODEL, help=f"OpenRouter model id (default {MODEL})")
    ap.add_argument("--save", help="write the request, answer and cost to this JSON file")
    args = ap.parse_args()

    if args.prompt:
        prompt = args.prompt
    elif args.prompt_file:
        prompt = Path(args.prompt_file).read_text()
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read()
    else:
        fail("give --prompt, --prompt-file or a prompt on stdin")
    if not prompt.strip():
        fail("the prompt is empty")
    if args.cap <= 0:
        fail("--cap must be positive")

    key = load_key()
    p_in, p_out, p_reason = prices(args.model)
    p_out_max = max(p_out, p_reason)
    est_in = math.ceil((len(prompt) + len(args.system or "")) / CHARS_PER_TOKEN) + OVERHEAD_TOKENS
    est_in_cost = est_in * p_in
    max_tokens = math.floor((args.cap - est_in_cost) / p_out_max)
    if max_tokens < MIN_OUTPUT_TOKENS:
        fail(f"a ${args.cap:.4f} cap leaves only {max(max_tokens, 0)} output tokens after a prompt of about "
             f"{est_in} tokens; raise --cap or shorten the prompt")

    messages = ([{"role": "system", "content": args.system}] if args.system else []) + [
        {"role": "user", "content": prompt}]
    body = {"model": args.model, "messages": messages, "max_tokens": max_tokens,
            "usage": {"include": True}, "reasoning": {"effort": args.effort, "exclude": True}}
    if args.temperature is not None:
        body["temperature"] = args.temperature

    print(f"{args.model}: cap ${args.cap:.4f}, prompt about {est_in} tokens, max_tokens {max_tokens}", file=sys.stderr)
    t0 = time.time()
    resp = request("POST", "/chat/completions", key, body)
    secs = time.time() - t0

    choice = (resp.get("choices") or [{}])[0]
    answer = (choice.get("message") or {}).get("content") or ""
    usage = resp.get("usage") or {}
    cost = usage.get("cost")
    if cost is None:
        cost = usage.get("prompt_tokens", 0) * p_in + usage.get("completion_tokens", 0) * p_out_max
    reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)

    print(answer)
    line = (f"cost ${cost:.4f} of ${args.cap:.4f} cap: {usage.get('prompt_tokens', '?')} in, "
            f"{usage.get('completion_tokens', '?')} out ({reasoning} reasoning), {secs:.1f}s")
    if choice.get("finish_reason") == "length":
        line += "; the answer hit max_tokens and is cut off"
    print(line, file=sys.stderr)

    if args.save:
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_text(json.dumps({
            "api": "openrouter", "model": args.model, "request": body, "answer": answer,
            "finish_reason": choice.get("finish_reason"), "usage": usage, "cost_usd": cost,
            "cap_usd": args.cap, "seconds": round(secs, 1), "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=2) + "\n")
        print(f"saved {args.save}", file=sys.stderr)


if __name__ == "__main__":
    main()
