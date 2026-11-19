#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx==0.28.1", "pillow==11.3.0"]
# ///
"""Generate images through OpenRouter (https://openrouter.ai/docs/guides/overview/multimodal/image-generation).

    or_image.py --prompt "..." --aspect 16:9 --out images                    # FLUX 3 Klein, about 2 MP
    or_image.py --prompt-file prompt.md --ref photo.png --out images         # edit from a reference
    or_image.py gpt --variant sunburst --prompt "..." --quality high --out images
    or_image.py some-author/some-model --prompt "..." --out images            # any image model slug
    or_image.py --costs images                                                # what past runs cost
    or_image.py --models                                                      # every image model slug

Models: an alias below or any slug from --models. The default is klein.
    klein  black-forest-labs/flux-3-image-klein  (768/1K/1.5K/2K/4K, up to 10 refs, cheapest)
    nano   google/gemini-nano-banana-2.1         (1K/2K/4K, up to 14 refs)
    gpt    openai/gpt-image-2.6-<flare|sunburst> (aspect ratio only, no size tiers; up to 16 refs)

The default --size is 1.5K, about 2 megapixels (1K is about 1 MP, 2K about 4 MP).
Every option is checked against what the model's endpoint accepts: an option you pass that the model
does not take is an error, a default it does not take is left out. --n above the model's per-request
limit is split into parallel requests. Local --ref images are inlined as data URLs, re-encoded to a
95% JPEG first when over 3 MB or 2560 px. A --prompt-file ending in .md uses its first ``` code block.
Images are saved as PNG by default; a model that only answers in JPEG is re-wrapped as PNG.
Each run saves <out>/<name>-<stamp>-<i>.<ext> plus <name>-<stamp>.json with the request and the real
cost OpenRouter reports, and prints that cost. Image requests are synchronous, so there is no resume:
OpenRouter does not bill a request whose result never reached you.
--set key=value overrides any request field; dotted keys reach nested ones (provider.options.openai.moderation=low).

The API key is OPENROUTER_API_KEY from the environment, else from the .env file next to this skill.
"""
import argparse
import base64
import concurrent.futures
import io
import json
import mimetypes
import os
import sys
import time
from pathlib import Path

import httpx

SKILL_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = SKILL_DIR / ".env"
API = "https://openrouter.ai/api/v1"
APP_HEADERS = {"X-OpenRouter-Title": "create-image"}

ALIASES = {"klein": "black-forest-labs/flux-3-image-klein", "nano": "google/gemini-nano-banana-2.1"}
GPT = "openai/gpt-image-2.6-{variant}"
DEFAULT_MODEL = "klein"
DEFAULT_SIZE = "1.5K"

# Local images bigger than this are re-encoded before being inlined as data URLs, so several
# large PNG references do not make a request body OpenRouter refuses.
INLINE_IMAGE_MAX_BYTES = 3 * 1024 * 1024
INLINE_IMAGE_MAX_EDGE = 2560


# --- plumbing -------------------------------------------------------------------------------------

def fail(msg):
    sys.exit(f"error: {msg}")


def load_key():
    """OPENROUTER_API_KEY from the environment, else from the skill's .env."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key and ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() == "OPENROUTER_API_KEY":
                    key = v.strip().strip('"').strip("'")
    if not key:
        fail(f"OPENROUTER_API_KEY is not set; export it or put it in {ENV_FILE}")
    return key


class ApiError(Exception):
    def __init__(self, status, body):
        self.status, self.body = status, body
        super().__init__(f"HTTP {status}: {body}")


def client(key=None, timeout=60.0):
    headers = dict(APP_HEADERS)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return httpx.Client(base_url=API, headers=headers, timeout=timeout, follow_redirects=True)


def call(http, method, path, **kw):
    """One API call; raises ApiError with OpenRouter's error message on a non-2xx answer."""
    r = http.request(method, path, **kw)
    if r.status_code >= 400:
        try:
            err = r.json().get("error", {})
            body = err.get("message") or json.dumps(err)
            meta = err.get("metadata")
            if meta:
                body += f" ({json.dumps(meta)[:600]})"
        except (ValueError, AttributeError):
            body = r.text[:800]
        raise ApiError(r.status_code, body)
    return r.json()


HINTS = {401: "Check OPENROUTER_API_KEY.",
         402: "The account needs credits: https://openrouter.ai/settings/credits",
         413: "The request body is too large; use fewer or smaller references.",
         429: "Rate limited; wait a moment and retry."}


def explain(e):
    """Print an ApiError with the hint that fits its status, then exit."""
    print(f"OpenRouter returned HTTP {e.status}: {e.body}", file=sys.stderr)
    if e.status in HINTS:
        print(HINTS[e.status], file=sys.stderr)
    sys.exit(1)


def is_remote(value):
    return value.startswith(("http://", "https://", "data:"))


def inline_image(path):
    """A data URL for a local image, re-encoded to a high-quality JPEG when it is too big to send as is."""
    if not os.path.isfile(path):
        fail(f"file not found: {path}")
    raw = Path(path).read_bytes()
    mime = mimetypes.guess_type(path)[0] or "image/png"
    from PIL import Image

    with Image.open(io.BytesIO(raw)) as im:
        w, h = im.size
        if len(raw) > INLINE_IMAGE_MAX_BYTES or max(w, h) > INLINE_IMAGE_MAX_EDGE:
            im = im.convert("RGB")
            im.thumbnail((INLINE_IMAGE_MAX_EDGE, INLINE_IMAGE_MAX_EDGE), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=95, subsampling=0)
            raw, mime = buf.getvalue(), "image/jpeg"
            print(f"inlined {path} as {im.size[0]}x{im.size[1]} JPEG, {len(raw) / 1e6:.1f} MB")
        else:
            print(f"inlined {path}, {len(raw) / 1e6:.1f} MB")
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


def read_prompt_file(path):
    """A .md prompt file holds the prompt in its first ``` code block, so notes can sit around it."""
    text = Path(path).read_text()
    if path.endswith(".md"):
        parts = text.split("```")
        if len(parts) < 3:
            fail(f"{path} has no ``` code block holding the prompt")
        block = parts[1]
        return block.split("\n", 1)[1].strip() if "\n" in block else block.strip()
    return text.strip()


def apply_sets(body, pairs):
    """--set key=value, with dotted keys for nested fields."""
    for pair in pairs:
        if "=" not in pair:
            fail(f"--set expects key=value, got {pair!r}")
        key, raw = pair.split("=", 1)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        parts, target = key.split("."), body
        for p in parts[:-1]:
            target = target.setdefault(p, {})
            if not isinstance(target, dict):
                fail(f"--set {key}: {p} is not an object")
        target[parts[-1]] = value


def redact(body):
    """The request as it is saved and printed: data URLs shortened, so records stay readable."""
    if isinstance(body, dict):
        return {k: redact(v) for k, v in body.items()}
    if isinstance(body, list):
        return [redact(v) for v in body]
    if isinstance(body, str) and body.startswith("data:"):
        return body.split(",", 1)[0] + f",<{len(body)} chars>"
    return body


def rel(path):
    """A path relative to the working directory when it is inside it, else absolute."""
    path, cwd = os.path.abspath(path), os.getcwd()
    return os.path.relpath(path, cwd) if path.startswith(cwd + os.sep) else path


def format_cost(cost):
    n = cost["outputs"]
    line = f"${cost['usd']:.4f} for {n} image{'' if n == 1 else 's'}"
    if n > 1:
        line += f" (${cost['per_output_usd']:.4f} each)"
    return line


def cost_entry(usd, outputs):
    outputs = max(outputs, 1)
    return {"usd": round(usd, 6), "per_output_usd": round(usd / outputs, 6), "outputs": outputs,
            "source": "openrouter usage"}


def report_costs(paths):
    """Total the cost of every OpenRouter image record under the given files or directories."""
    records = []
    for p in map(Path, paths):
        for f in sorted(p.rglob("*.json") if p.is_dir() else [p]):
            try:
                rec = json.loads(f.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(rec, dict) and rec.get("api") == "openrouter" and rec.get("kind") == "image":
                records.append((f, rec))
    if not records:
        fail("no OpenRouter image records found")
    total, missing = 0.0, 0
    for f, rec in records:
        if "cost" in rec:
            total += rec["cost"]["usd"]
            label = format_cost(rec["cost"])
        else:
            missing += 1
            label = "unknown"
        print(f"{label:<42} {rec['model']:<40} {rel(str(f)).removesuffix('.json')}")
    print(f"total: ${total:.4f} across {len(records) - missing} runs"
          + (f", {missing} without a cost" if missing else ""))


# --- image generation -----------------------------------------------------------------------------

def endpoint_params(slug):
    """(supported_parameters, passthrough keys) of the model's first endpoint."""
    author, _, name = slug.partition("/")
    with client() as http:
        try:
            data = call(http, "GET", f"/images/models/{author}/{name}/endpoints")
        except ApiError as e:
            if e.status == 404:
                fail(f"no image model {slug!r} on OpenRouter; list them with --models")
            explain(e)
    endpoints = data.get("endpoints") or fail(f"{slug} has no live endpoint")
    ep = endpoints[0]
    return ep.get("supported_parameters") or {}, ep.get("allowed_passthrough_parameters") or []


def check(params, name, value, flag, explicit):
    """True when the model takes this value. A value the user passed that it does not take is an error."""
    spec = params.get(name)
    ok = spec is not None and (spec.get("type") != "enum" or value in spec.get("values", []))
    if spec and spec.get("type") == "range" and isinstance(value, int):
        ok = spec.get("min", value) <= value <= spec.get("max", value)
    if not ok and explicit:
        if spec is None:
            fail(f"this model takes no {flag}")
        allowed = spec.get("values") or f"{spec.get('min')}-{spec.get('max')}"
        fail(f"{flag} must be one of {allowed} for this model, got {value!r}")
    return ok


def build(args, slug, params):
    req = {"model": slug, "prompt": args.prompt_text}

    def opt(name, value, flag, explicit):
        if value is not None and check(params, name, value, flag, explicit):
            req[name] = value

    if args.ref:
        limit = (params.get("input_references") or {}).get("max", 0)
        if len(args.ref) > limit:
            fail(f"this model takes up to {limit} reference images, got {len(args.ref)}")
        req["input_references"] = [{"type": "image_url", "image_url": {"url": p}} for p in args.ref]
    aspect = args.aspect or ("auto" if args.ref else "1:1")
    opt("aspect_ratio", aspect, "--aspect", bool(args.aspect))
    opt("resolution", args.size, "--size", args.size_explicit)
    opt("quality", args.quality, "--quality", args.quality_explicit)
    opt("output_format", args.format, "--format", args.format_explicit)
    opt("background", args.background, "--background", True)
    opt("seed", args.seed, "--seed", True)
    if args.provider:
        req["provider"] = {"only": args.provider}
    return req


def materialize(req):
    for item in req.get("input_references", []):
        slot = item["image_url"]
        if not is_remote(slot["url"]):
            slot["url"] = inline_image(slot["url"])


def to_png(raw):
    from PIL import Image

    buf = io.BytesIO()
    with Image.open(io.BytesIO(raw)) as im:
        im.save(buf, "PNG")
    return buf.getvalue()


def image_size(raw):
    from PIL import Image

    with Image.open(io.BytesIO(raw)) as im:
        return im.size


def generate(key, body):
    with client(key, timeout=900) as http:
        return call(http, "POST", "/images", json=body)


def list_models():
    with client() as http:
        data = call(http, "GET", "/images/models")
    for m in sorted(data.get("data", data), key=lambda m: m["id"]):
        alias = next((a for a, s in ALIASES.items() if s == m["id"]), "")
        alias = alias or ("gpt" if m["id"].startswith("openai/gpt-image-2.6-") else "")
        print(m["id"] + (f"  ({alias})" if alias else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model", nargs="?", default=DEFAULT_MODEL,
                    help="klein (default), nano, gpt, or an OpenRouter image model slug")
    ap.add_argument("--models", action="store_true", help="list image model slugs")
    ap.add_argument("--costs", nargs="+", metavar="PATH", help="report what past runs cost (files or directories)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--prompt")
    g.add_argument("--prompt-file")
    ap.add_argument("--ref", action="append", default=[], help="reference image path or URL, repeatable")
    ap.add_argument("--out", help="output directory (required to generate)")
    ap.add_argument("--name", help="file name prefix (default: prompt file name, else the model)")
    ap.add_argument("--n", type=int, default=1, help="images per run (1-10, default 1)")
    ap.add_argument("--aspect", help="aspect ratio such as 16:9 (default 1:1, or auto with --ref)")
    ap.add_argument("--size", choices=["512", "768", "1K", "1.5K", "2K", "4K"],
                    help=f"resolution tier (default {DEFAULT_SIZE}, about 2 MP)")
    ap.add_argument("--quality", choices=["auto", "low", "medium", "high", "xhigh", "max"],
                    help="gpt quality, the main gpt cost lever (default high)")
    ap.add_argument("--variant", choices=["flare", "sunburst"],
                    help="gpt: flare is the fast default, sunburst is slower with more fine detail")
    ap.add_argument("--format", choices=["png", "jpeg", "webp"], help="output format (default png)")
    ap.add_argument("--background", choices=["auto", "transparent", "opaque"])
    ap.add_argument("--seed", type=int)
    ap.add_argument("--provider", action="append", metavar="SLUG", help="route only to this provider, repeatable")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="override a request field; dotted keys for nested fields; JSON values parsed")
    ap.add_argument("--dry-run", action="store_true", help="print the request, read no files, submit nothing")
    args = ap.parse_args()

    if args.models:
        list_models()
        return
    if args.costs:
        report_costs(args.costs)
        return
    if not args.out and not args.dry_run:
        ap.error("--out is required")
    if not 1 <= args.n <= 10:
        ap.error("--n must be 1 to 10")
    if args.variant and args.model != "gpt":
        ap.error("--variant only applies to gpt")
    args.prompt_text = args.prompt or (read_prompt_file(args.prompt_file) if args.prompt_file else None)
    if not args.prompt_text:
        ap.error("--prompt or --prompt-file is required")
    args.size_explicit, args.quality_explicit, args.format_explicit = bool(args.size), bool(args.quality), bool(args.format)
    args.size, args.quality, args.format = args.size or DEFAULT_SIZE, args.quality or "high", args.format or "png"

    slug = GPT.format(variant=args.variant or "flare") if args.model == "gpt" else ALIASES.get(args.model, args.model)
    params, _ = endpoint_params(slug)
    req = build(args, slug, params)
    apply_sets(req, args.set)

    per_request = max(1, (params.get("n") or {}).get("max", 1))
    batches = [min(per_request, args.n - i) for i in range(0, args.n, per_request)]
    shown = {k: v for k, v in req.items() if k not in ("model", "prompt", "input_references", "provider")}
    print(f"model {slug}, {args.n} image{'s' if args.n > 1 else ''} in {len(batches)} request"
          f"{'s' if len(batches) > 1 else ''}, {json.dumps(shown)}, prompt {len(args.prompt_text)} chars")
    for i, path in enumerate(args.ref, 1):
        print(f"  ref {i}: {path}")
    if args.dry_run:
        print(json.dumps(redact(dict(req, n=batches[0]) if batches[0] > 1 else req), indent=2))
        return

    os.makedirs(args.out, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = args.name or (os.path.splitext(os.path.basename(args.prompt_file))[0] if args.prompt_file
                         else args.model.split("/")[-1])
    base = f"{name}-{stamp}"
    record = {"api": "openrouter", "kind": "image", "model": slug, "submitted": stamp,
              "references": [{"as": f"ref {i}", "file": p} for i, p in enumerate(args.ref, 1)],
              "input": redact(req)}
    key = load_key()
    materialize(req)

    files, usd, errors = [], 0.0, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(batches), 4)) as pool:
        jobs = [pool.submit(generate, key, dict(req, n=b) if b > 1 or "n" in params else req) for b in batches]
        for job in jobs:
            try:
                res = job.result()
            except ApiError as e:
                errors.append(f"HTTP {e.status}: {e.body}")
                print(f"request failed: HTTP {e.status}: {e.body}" + (f" ({HINTS[e.status]})" if e.status in HINTS else ""))
                continue
            usd += float((res.get("usage") or {}).get("cost") or 0)
            for item in res.get("data", []):
                raw = base64.b64decode(item["b64_json"])
                mime = item.get("media_type") or f"image/{args.format}"
                if args.format == "png" and mime in ("image/jpeg", "image/webp"):
                    # Models without an output_format option answer in JPEG; re-wrap losslessly as PNG
                    # so every output has the format asked for.
                    raw, mime = to_png(raw), "image/png"
                    record.setdefault("converted_to_png", True)
                ext = {"image/jpeg": ".jpg"}.get(mime) or mimetypes.guess_extension(mime) or ".png"
                path = os.path.join(args.out, f"{base}-{len(files) + 1}{ext}")
                Path(path).write_bytes(raw)
                files.append(rel(path))
                w, h = image_size(raw)
                print(f"#{len(files)}: {rel(path)} ({w}x{h}, {w * h / 1e6:.1f} MP)")

    if not files:
        fail("no image came back" + (f": {errors[0]}" if errors else ""))
    record["files"] = files
    if errors:
        record["errors"] = errors
    record["cost"] = cost_entry(usd, len(files))
    Path(args.out, f"{base}.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"cost: {format_cost(record['cost'])}")


if __name__ == "__main__":
    main()
