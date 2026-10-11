"""Run the agent on one task from the command line, from the repository root.

    python3 -m agent "Which source IP had the most failed SSH password attempts, and how many?" \\
        --data lab02/partA/data --tools run_shell --schema lab02/partA/answer.schema.json \\
        --transcript lab02/partA/transcript.json --max-steps 6

The system prompt is prompts.build() over the tools and the --system-file
files; --show-prompt prints it and stops. Every shell command waits at a
[gate] line on this terminal: y runs it, n refuses it, and the words after n
reach the model as your reason. --yes answers y to every gate. The trace goes
to stderr, the answer to stdout, and --transcript writes the run as JSON
after every event and again at the end.

Lab 3 adds --memory, --session and --max-messages; lab 4 adds --mcp; lab 5
adds --guards.
"""
import argparse
import json
import os
import shlex
import sys

from . import client, loop, prompts, tools


def one_line(text, limit=240):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit] + " ..."


class Recorder:
    """What a run shows and keeps: the gate on this terminal, the trace on
    stderr and the transcript on disk."""

    def __init__(self, args, tool_names):
        self.path = args.transcript
        self.step = 0
        self.total = 0
        self.transcript = {"task": args.task, "answer": None, "stop": None, "steps": 0, "events": [],
                           "usage": {"input": 0, "output": 0, "calls": 0}, "gate": [],
                           "yes_flag": args.yes, "tools": tool_names,
                           "system_files": list(args.system_file), "max_steps": args.max_steps,
                           "max_tokens": args.max_tokens, "answer_attempts": None, "messages": []}

    def complete(self, messages, tools=None, response_schema=None):
        """client.complete(), keeping the message list the loop sends so the
        transcript can be written before the run ends."""
        self.transcript["messages"] = messages
        return client.complete(messages, tools=tools, response_schema=response_schema)

    def ask_user(self, command):
        """The permission gate: y runs the command; n, or n with a reason, refuses it."""
        print(f"[gate] run '{command}'? [y/N, or n <reason>] ", end="", file=sys.stderr, flush=True)
        line = sys.stdin.readline() if sys.stdin else ""
        if not (sys.stdin and sys.stdin.isatty()):
            print(line.strip(), file=sys.stderr)  # a piped answer, echoed so the trace reads as typed
        word, _, rest = line.strip().partition(" ")
        allowed = word.lower() in ("y", "yes")
        if allowed:
            reason = ""
        elif word.lower() in ("n", "no"):
            reason = rest.strip()
        else:
            reason = line.strip()  # anything but y refuses; the whole line is the reason
        self.transcript["gate"].append({"step": self.step, "command": command,
                                        "answer": "y" if allowed else "n", "reason": reason})
        self.save()
        return True if allowed else (reason or False)

    def on_event(self, event):
        """One trace line per event, then the transcript on disk."""
        step = event.get("step", self.step)
        if event["type"] == "model":
            self.step = step
            usage = event.get("usage") or {}
            used = self.transcript["usage"]
            used["input"] += usage.get("input", 0)
            used["output"] += usage.get("output", 0)
            used["calls"] += 1
            self.total += usage.get("input", 0) + usage.get("output", 0)
            print(f"[step {step}] model: {usage.get('input', 0):,} in, {usage.get('output', 0):,} out; "
                  f"total {self.total:,}", file=sys.stderr)
            if event.get("tool_calls"):
                print(f"[step {step}] thought: {one_line(event.get('text')) or '(none from this provider)'}",
                      file=sys.stderr)
        elif event["type"] == "tool_call":
            state = "denied" if event["denied"] else ("ok" if event["ok"] else "error")
            chars = self.observation_chars(event)
            raw = event.get("raw_chars")
            clipped = f" (clipped from {raw:,})" if isinstance(raw, int) and raw > chars else ""
            print(f"[step {step}] {event['name']}({json.dumps(event['arguments'])}) -> {state}, "
                  f"{chars:,} chars{clipped}", file=sys.stderr)
        else:  # retry, window, correction, compaction: the events later labs add
            print(f"[step {step}] {event['type']}: "
                  + json.dumps({k: v for k, v in event.items() if k not in ("type", "step")}),
                  file=sys.stderr)
        self.transcript["events"].append(event)
        self.transcript["steps"] = step
        self.save()

    def observation_chars(self, event):
        """Length of the tool message the model reads for this call: the
        event's result, unless loop.RESULT_CHARS cut it; then the message
        itself, when the list the loop last sent holds it."""
        result = event.get("result") or ""
        if len(result) < loop.RESULT_CHARS:
            return len(result)
        for m in reversed(self.transcript["messages"]):
            if m.get("role") == "tool" and m.get("tool_call_id") == event["id"]:
                return len(m.get("content") or "")
        return len(result)

    def save(self):
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.transcript, f, indent=2, ensure_ascii=False)

    def partial(self, stop):
        """The run as recorded so far, shaped like loop.run()'s result."""
        t = self.transcript
        return {"answer": None, "stop": stop, "steps": t["steps"], "messages": t["messages"],
                "events": t["events"], "usage": t["usage"]}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m agent", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task", nargs="?", metavar="TASK", help="the question for the agent, sent as the user message")
    ap.add_argument("--data", default=".", metavar="DIR",
                    help="the data directory: every command runs there (default: current)")
    ap.add_argument("--tools", default="run_shell", metavar="NAMES",
                    help="comma-separated tool names (default: run_shell)")
    ap.add_argument("--system-file", action="append", default=[], metavar="PATH",
                    help="add the file's text to the system prompt under ## <file name>; repeatable")
    ap.add_argument("--max-steps", type=int, default=8, metavar="N",
                    help="the step cap: at most this many model calls (default 8)")
    ap.add_argument("--max-tokens", type=int, metavar="N",
                    help="part B: stop before a model call once the run has used this many tokens")
    ap.add_argument("--schema", metavar="FILE",
                    help="JSON schema file the final answer must match (asked again when it does not)")
    ap.add_argument("--transcript", metavar="FILE", help="write the run as JSON to this file, after every event")
    ap.add_argument("--yes", action="store_true", help="answer y at every gate; the transcript records yes_flag")
    ap.add_argument("--show-prompt", action="store_true",
                    help="print the system prompt, and the task when one is given, then stop")
    ap.add_argument("--memory", metavar="DIR", help="lab 3: directory of session-*.json memory files")
    ap.add_argument("--session", default="1", metavar="ID", help="lab 3: id of this session (default 1)")
    ap.add_argument("--max-messages", type=int, metavar="N", help="lab 3: compact when the message list is longer")
    ap.add_argument("--mcp", metavar="COMMAND",
                    help="lab 4: command line that starts an MCP server whose tools join the loop")
    ap.add_argument("--guards", action="store_true", help="lab 5: enable guards.py")
    args = ap.parse_args(argv)

    if args.task is None and not args.show_prompt:
        ap.error("the following arguments are required: TASK")
    if not os.path.isdir(args.data):
        ap.error(f"--data {args.data}: no such directory")
    for path in args.system_file:
        if not os.path.isfile(path):
            ap.error(f"--system-file {path}: no such file")
    schema = None
    if args.schema:
        try:
            with open(args.schema, encoding="utf-8") as f:
                schema = json.load(f)
        except (OSError, ValueError) as e:
            ap.error(f"--schema {args.schema}: {e}")

    try:
        tool_list = tools.get([n for n in args.tools.split(",") if n])
    except KeyError as e:
        ap.error(e.args[0])
    if args.mcp:
        tool_list += tools.mcp_tools(shlex.split(args.mcp))
    recorder = Recorder(args, [t["name"] for t in tool_list])
    tools.configure(data_dir=args.data, ask=(lambda command: True) if args.yes else recorder.ask_user,
                    guards=args.guards)

    system = prompts.build(tool_list, extra_files=args.system_file)
    store = compact = None
    if args.memory:
        from . import memory
        store = memory.Store(args.memory, args.session)
        earlier = store.load_all()
        system += memory.facts_block(earlier)
        print(f"[memory] {len(earlier)} fact(s) loaded from {args.memory}", file=sys.stderr)
    if args.max_messages:
        from . import memory
        compact = lambda msgs: memory.compact(msgs, client.complete, store)  # noqa: E731

    if args.show_prompt:
        print(system)
        if args.task is not None:
            print("\n--- task (the user message) ---")
            print(args.task)
        print(f"[prompt] {len(system):,} characters", file=sys.stderr)
        return 0

    if args.yes:
        print("[gate] --yes: every command runs without asking", file=sys.stderr)
    recorder.save()
    try:
        result = loop.run(args.task, recorder.complete, tool_list, system=system,
                          max_steps=args.max_steps, max_tokens=args.max_tokens,
                          on_event=recorder.on_event, compact=compact, max_messages=args.max_messages)
    except client.ProviderError as e:  # part A has no retry; part B's loop retries once
        print(f"[error] {e}", file=sys.stderr)
        result = recorder.partial("error")
    gate = recorder.transcript["gate"]
    print(f"[stop] {result['stop']} after {result['steps']} step(s); gate prompts: {len(gate)}", file=sys.stderr)

    answer_attempts = None
    if schema is not None and result["stop"] == "answer":
        try:
            obj, answer_attempts = client.finish_json(result["messages"], result["answer"], schema)
            result["answer"] = json.dumps(obj)
            if len(answer_attempts) > 1:
                print(f"[schema] schema-valid after {len(answer_attempts)} attempt(s)", file=sys.stderr)
        except client.SchemaError as e:
            answer_attempts = e.attempts
            result["stop"] = "schema"
            print(f"[schema] no schema-valid answer after {len(answer_attempts)} attempt(s); last errors: "
                  f"{'; '.join(answer_attempts[-1]['errors'])}", file=sys.stderr)
        except client.ProviderError as e:
            print(f"[error] {e}", file=sys.stderr)
            result["stop"] = "error"
        if answer_attempts and any(a.get("schema_fallback") for a in answer_attempts):
            print("[schema] the provider refused response_format; the reply text was checked "
                  "against the schema instead", file=sys.stderr)
    print(result["answer"] if result["answer"] is not None else "(no answer)")

    if store is not None:
        from . import memory
        try:
            store.facts.extend(memory.extract_facts(result["messages"], client.complete))
        except client.ProviderError as e:  # the facts gathered so far are still saved
            print(f"[error] {e}", file=sys.stderr)
            result["stop"] = "error"
        print(f"[memory] {len(store.facts)} fact(s) saved to {store.save()}", file=sys.stderr)

    recorder.transcript.update(answer=result["answer"], stop=result["stop"], steps=result["steps"],
                               events=result.get("events", recorder.transcript["events"]),
                               usage=result.get("usage", recorder.transcript["usage"]),
                               answer_attempts=answer_attempts,
                               messages=result.get("messages", recorder.transcript["messages"]))
    if args.transcript:
        recorder.save()
        print(f"[transcript] {args.transcript}", file=sys.stderr)
    return 0 if result["stop"] == "answer" else 1


if __name__ == "__main__":
    sys.exit(main())
