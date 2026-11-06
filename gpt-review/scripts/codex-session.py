#!/usr/bin/env python3
"""Report what a Codex TUI running in an hc terminal actually did, from its own session log.

Usage: codex-session.py <hc terminal name or address>

Finds the rollout file the Codex process has open (via lsof on the pid hc reports)
and prints JSON: the rollout path, the model, effort, sandbox and approval policy of
every turn, whether the last turn completed, and its final answer exactly as Codex
produced it (raw Markdown). Exits 1 when the session cannot be located.
"""

import json
import subprocess
import sys


def fail(message):
    print(json.dumps({"error": message}))
    sys.exit(1)


def rollout_path(terminal):
    try:
        info = json.loads(subprocess.run(["hc", "get", terminal, "--json"], capture_output=True, text=True, check=True).stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as error:
        fail(f"hc get {terminal} failed: {error}")
    pid = (info.get("foreground") or {}).get("pid") or info.get("pid")
    if not pid:
        fail(f"{terminal} has no running process (state: {info.get('state')})")
    lsof = subprocess.run(["lsof", "-p", str(pid), "-Fn"], capture_output=True, text=True).stdout
    paths = [line[1:] for line in lsof.splitlines() if line.startswith("n") and "/.codex/sessions/" in line and line.endswith(".jsonl")]
    if not paths:
        fail(f"pid {pid} of {terminal} has no Codex session file open; is it Codex, and has it started?")
    return paths[-1]


def main():
    if len(sys.argv) != 2:
        fail("usage: codex-session.py <hc terminal>")
    path = rollout_path(sys.argv[1])
    turns, started, completed, aborted, errors = [], [], {}, [], []
    with open(path) as rollout:
        for line in rollout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = event.get("payload") or {}
            kind = event.get("type")
            subtype = payload.get("type")
            if kind == "turn_context":
                turns.append({
                    "model": payload.get("model"),
                    "effort": payload.get("effort"),
                    "sandbox": (payload.get("sandbox_policy") or {}).get("type"),
                    "approval": payload.get("approval_policy"),
                })
            elif kind == "event_msg" and subtype == "task_started":
                started.append(payload.get("turn_id"))
            elif kind == "event_msg" and subtype == "task_complete":
                completed[payload.get("turn_id")] = payload.get("last_agent_message")
            elif kind == "event_msg" and subtype in ("turn_aborted", "error", "stream_error"):
                (aborted if subtype == "turn_aborted" else errors).append(payload.get("message") or payload.get("reason") or subtype)
    last_turn = started[-1] if started else None
    print(json.dumps({
        "rollout": path,
        "turns": turns,
        "last_turn_completed": last_turn is not None and last_turn in completed,
        "aborted": aborted,
        "errors": errors,
        "final_answer": completed.get(last_turn),
    }, indent=2))


main()
