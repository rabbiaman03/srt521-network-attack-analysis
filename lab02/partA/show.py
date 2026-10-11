#!/usr/bin/env python3
"""Print a transcript that python3 -m agent --transcript wrote. Run from the repository root:

    python3 lab02/partA/show.py lab02/partA/transcript.json
    python3 lab02/partA/show.py --project lab02/partA/transcript.json

The first form prints the run for a reader: the first twelve lines of the
system prompt and the text of every --system-file, the trace with the first
lines of each observation, the tokens per step, the gate answers with their
reasons, and the stop reason. --project prints the projection the
instructor's tests compare, as stable JSON: the task, the answer, the stop
reason, the steps, the type and name of every event, the gate entries and
the usage keys.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HEAD_LINES = 12
PREVIEW_LINES = 3


def project(t):
    """The fields of a run that stay the same from one run of the same model to the next."""
    return {"task": t.get("task"), "answer": t.get("answer"), "stop": t.get("stop"), "steps": t.get("steps"),
            "events": [{"type": e.get("type"), "name": e["name"]} if "name" in e else {"type": e.get("type")}
                       for e in t.get("events") or []],
            "gate": t.get("gate") or [],
            "usage": sorted(t.get("usage") or {})}


def observation(t, event):
    """The tool message the model read for this call, or the event's result."""
    for m in t.get("messages") or []:
        if m.get("role") == "tool" and m.get("tool_call_id") == event.get("id"):
            return m.get("content") or ""
    return event.get("result") or ""


def preview(text):
    """The first lines of an observation: a shell result's exit code and output, or the text."""
    try:
        obj = json.loads(text)
    except ValueError:
        obj = None
    if isinstance(obj, dict) and "output" in obj:
        head, lines = f"exit {obj.get('exit_code')}", str(obj["output"]).splitlines()
    else:
        head, lines = None, text.splitlines()
    shown = lines[:PREVIEW_LINES]
    shown += [line for line in lines[PREVIEW_LINES:] if "characters elided" in line]  # a clipped observation
    out = ([head] if head else []) + shown
    if len(lines) > len(shown):
        out.append(f"... {len(lines) - len(shown):,} more line(s)")
    return out


def show(t, path):
    print(f"transcript: {path}")
    print(f"task: {t.get('task')}")
    print(f"tools: {', '.join(t.get('tools') or [])}; --system-file: {', '.join(t.get('system_files') or []) or 'none'}; "
          f"--max-steps {t.get('max_steps')}; --max-tokens {t.get('max_tokens')}; --yes: {'yes' if t.get('yes_flag') else 'no'}")

    messages = t.get("messages") or []
    system = (messages[0].get("content") or "") if messages and messages[0].get("role") == "system" else ""
    lines = system.splitlines()
    print(f"\nsystem prompt: {len(system):,} characters, {len(lines)} line(s); the first {min(HEAD_LINES, len(lines))}:")
    for line in lines[:HEAD_LINES]:
        print(f"  | {line}")
    if len(lines) > HEAD_LINES:
        print(f"  | ... {len(lines) - HEAD_LINES} more line(s)")
    files = t.get("system_files") or []
    if files:  # the extra files end the prompt: print it from the first one's heading on
        found = [system.find(f"## {os.path.basename(name)}") for name in files]
        print(f"from --system-file {', '.join(files)}:")
        tail = system[min(found):] if min(found) >= 0 else f"(no ## {os.path.basename(files[0])} heading in the prompt)"
        for line in tail.splitlines():
            print(f"  | {line}")

    print("\ntrace:")
    gate = list(t.get("gate") or [])
    unasked = list(gate)
    total = 0
    tokens = []
    for e in t.get("events") or []:
        step = e.get("step")
        if e.get("type") == "model":
            usage = e.get("usage") or {}
            total += usage.get("input", 0) + usage.get("output", 0)
            tokens.append((step, usage.get("input", 0), usage.get("output", 0)))
            print(f"[step {step}] model: {usage.get('input', 0):,} in, {usage.get('output', 0):,} out; total {total:,}")
            if e.get("tool_calls"):
                text = " ".join((e.get("text") or "").split())
                print(f"[step {step}] thought: {text or '(none from this provider)'}")
        elif e.get("type") == "tool_call":
            command = (e.get("arguments") or {}).get("command")
            asked = next((g for g in unasked if g.get("step") == step and g.get("command") == command), None)
            if asked:
                unasked.remove(asked)
                reason = f" {asked['reason']}" if asked.get("reason") else ""
                print(f"[gate] run '{command}'? {asked.get('answer')}{reason}")
            state = "denied" if e.get("denied") else ("ok" if e.get("ok") else "error")
            text = observation(t, e)
            raw = e.get("raw_chars")
            clipped = f" (clipped from {raw:,})" if isinstance(raw, int) and raw > len(text) else ""
            print(f"[step {step}] {e.get('name')}({json.dumps(e.get('arguments'))}) -> {state}, {len(text):,} chars{clipped}")
            for line in preview(text):
                print(f"         {line}")
        else:  # retry, window, correction, compaction: the events later labs add
            print(f"[step {step}] {e.get('type')}: "
                  + json.dumps({k: v for k, v in e.items() if k not in ("type", "step")}))
    print(f"[stop] {t.get('stop')} after {t.get('steps')} step(s); gate prompts: {len(gate)}")

    print("\ntokens per step (input, output):")
    for step, n_in, n_out in tokens:
        print(f"  step {step}: {n_in:,} in, {n_out:,} out")
    usage = t.get("usage") or {}
    print(f"  total: {usage.get('input', 0):,} in, {usage.get('output', 0):,} out, {usage.get('calls', 0)} call(s)")

    print(f"\ngate answers: {len(gate)}")
    for g in gate:
        reason = f"  (reason: {g['reason']})" if g.get("reason") else ""
        print(f"  step {g.get('step')}: {g.get('answer')}  {g.get('command')}{reason}")

    attempts = t.get("answer_attempts") or []
    if len(attempts) > 1:
        print(f"\nschema: {len(attempts)} answer attempt(s); the first failed with: {'; '.join(attempts[0].get('errors') or [])}")
    if any(a.get("schema_fallback") for a in attempts):
        print("schema: the provider refused response_format; the reply text was checked against the schema instead")
    print(f"\nstop: {t.get('stop')} after {t.get('steps')} step(s)")
    print(f"answer: {t.get('answer')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcript", help="the JSON file written by python3 -m agent --transcript")
    ap.add_argument("--project", action="store_true", help="print the projection the tests compare, as JSON")
    args = ap.parse_args()
    path = args.transcript
    if not os.path.exists(path) and os.path.exists(os.path.join(ROOT, path)):
        path = os.path.join(ROOT, path)  # a path given from the repository root, run from elsewhere
    try:
        with open(path, encoding="utf-8") as f:
            t = json.load(f)
    except (OSError, ValueError) as e:
        sys.exit(f"cannot read {args.transcript}: {e}")
    if args.project:
        print(json.dumps(project(t), indent=2, sort_keys=True, ensure_ascii=False))
    else:
        show(t, args.transcript)
    return 0


if __name__ == "__main__":
    sys.exit(main())
