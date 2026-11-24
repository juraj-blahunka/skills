#!/bin/bash
# Start both reviews of one change in parallel: a fresh Opus Claude agent and GPT-6-Luna in a read-only Codex.
#
# Usage: review.sh <id> <title> <base> <head> <intended behavior> [repo or worktree]
#
# Needs: MANAGER_DIR (the manager's scratchpad), HC_TERMINAL_ID (the manager's hc address).
# GPT_EFFORT overrides the GPT reasoning effort (default medium; high for large diffs).
# OPUS=0 skips the Opus review (small, low-risk items): GPT only.
#
# Writes $MANAGER_DIR/<id>-brief-opus.md and <id>-brief-gpt.md.
# Opus writes its findings to $MANAGER_DIR/<id>-review-opus.md and reports with hc send.
# GPT runs as hc terminal gpt-<id>; collect its answer with
#   python3 ~/.claude/skills/gpt-review/scripts/codex-session.py gpt-<id>
set -euo pipefail

S=${MANAGER_DIR:?set MANAGER_DIR to the manager scratchpad}
me=${HC_TERMINAL_ID:?not running inside Herdr}
[ $# -ge 5 ] || { echo "usage: review.sh <id> <title> <base> <head> <intent> [repo]" >&2; exit 64; }
id=$1 title=$2 base=$3 head=$4 intent=$5 repo=${6:-$PWD}
effort=${GPT_EFFORT:-medium}
template="$(cd "$(dirname "$0")/.." && pwd)/templates/review-brief.md"

git -C "$repo" rev-parse --verify -q "$base^{commit}" >/dev/null || { echo "unknown base $base in $repo" >&2; exit 1; }
git -C "$repo" rev-parse --verify -q "$head^{commit}" >/dev/null || { echo "unknown head $head in $repo" >&2; exit 1; }

# Values go through the environment, so a | or & in the intent cannot break the substitution.
render() {
	TITLE=$title BASE=$base HEAD=$head INTENT=$intent REPO=$repo OUTPUT=$1 python3 -I -c '
import os, sys
text = open(sys.argv[1]).read()
for key in ("TITLE", "BASE", "HEAD", "INTENT", "REPO", "OUTPUT"):
    text = text.replace("{{" + key + "}}", os.environ[key])
sys.stdout.write(text)
' "$template"
}

opus_brief=$S/$id-brief-opus.md
gpt_brief=$S/$id-brief-gpt.md
render "Write your findings to $S/$id-review-opus.md as a list." >"$opus_brief"
render "Give your whole review as your final answer, as a list. Your sandbox is read-only: do not write files and do not reply through hc." >"$gpt_brief"
for f in "$opus_brief" "$gpt_brief"; do
	[ -s "$f" ] || { echo "empty brief $f" >&2; exit 1; }
done

if [ "${OPUS:-1}" != 0 ]; then
	hc run --bg --json --name "review-$id" --cwd "$repo" claude --permission-mode auto --model opus \
		"Read and follow $opus_brief. You may write only the findings file it names. Report with hc send $me \"DONE $id opus review\" when done." >/dev/null
	echo "opus: review-$id"
else
	echo "opus: skipped (OPUS=0)"
fi

supported=$(codex debug models | python3 -I -c 'import json,sys; m=next((m for m in json.load(sys.stdin)["models"] if m["slug"]=="gpt-6-luna"),None); print(" ".join(e["effort"] for e in m["supported_reasoning_levels"]) if m else "")')
case " $supported " in
	*" $effort "*) ;;
	*) echo "gpt-6-luna with effort $effort is not in the Codex catalog ($supported); GPT review not started" >&2; exit 1 ;;
esac

start_codex() {
	hc rm "gpt-$id" >/dev/null 2>&1 || true
	hc run --bg --json --name "gpt-$id" --cwd "$repo" \
		codex --no-alt-screen -m gpt-6-luna -c model_reasoning_effort="$effort" -s read-only -a never >/dev/null
	hc wait "gpt-$id" --timeout 60 >/dev/null || true
	hc get "gpt-$id" --json | python3 -I -c 'import json,sys; d=json.load(sys.stdin); s=d.get("status"); s=s.get("state") if isinstance(s,dict) else s; sys.exit(0 if d.get("state")=="live" and s=="idle" else 1)'
}

# Codex may update itself on launch and exit ("Please restart Codex"): relaunch once.
start_codex || start_codex || { echo "Codex did not start in gpt-$id; hc read gpt-$id" >&2; exit 1; }
hc send "gpt-$id" "$(cat "$gpt_brief")" >/dev/null
echo "gpt: gpt-$id ($effort)"
