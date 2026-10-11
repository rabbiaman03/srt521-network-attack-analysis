#!/usr/bin/env python3
"""Lab 2 part A checker. Run from the repository root:

    python3 lab02/partA/check.py                 # every case: 15 offline, then the 2 transcripts
    python3 lab02/partA/check.py -k prompts      # only the cases labelled prompts; -k repeats
    python3 lab02/partA/check.py --offline       # skip the transcript cases
    python3 lab02/partA/check.py --live          # add the live case: your loop through your provider
    python3 lab02/partA/check.py --debug -k loop # let a breakpoint() in agent/ stop a case at (Pdb)

A case's label is the word before the colon: prompts, dispatch, loop, gate,
run_shell, transcript (and live). The offline cases drive your code with
agent.fake.FakeModel, so they need no key and give the same result every
time. Each case prints PASS or FAIL with the reason, and the last line counts
them; the exit status is 0 only when every case passes.

The checker runs with PYTHONBREAKPOINT=0, so a breakpoint() left in agent/
cannot stop a case; each one it finds is named in a note above the cases.
--debug turns breakpoint() back on and lifts the 20-second limit, so a
breakpoint() in the code a failing case runs stops it at a (Pdb) prompt.
"""
import argparse
import ast
import inspect
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import tokenize
import traceback

BREAKPOINT_SETTING = os.environ.get("PYTHONBREAKPOINT")  # what --debug puts back
os.environ["PYTHONBREAKPOINT"] = "0"  # a breakpoint() left in agent/ must not stop a case
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from agent import client, loop, prompts, tools  # noqa: E402
from agent.fake import FakeModel  # noqa: E402

DATA = os.path.join("lab02", "partA", "data")
TRANSCRIPT = "lab02/partA/transcript.json"
RULES_TRANSCRIPT = "lab02/partA/transcript-rules.json"
RULES = "lab02/partA/rules.md"
TASK = "Which source IP had the most failed SSH password attempts, and how many?"
PIPELINE = 'grep "Failed password" auth.log | grep -oE "from [0-9.]+" | sort | uniq -c | sort -rn | head -1'
FAILED_RE = re.compile(r"Failed password for (?:invalid user )?\S+ from (\d+\.\d+\.\d+\.\d+)")
# A program no allowlist names: the gate is asked about it in part A and under part B's lists alike.
UNLISTED = "srt521-probe auth.log"
# The timeout case's command line, this run's own, so no other sleep on the machine counts as left over.
SLEEP = f"sleep 3.{os.getpid()}"
MARKERS = ("# Lab 3: compaction hook", "# Part B: budget check", "# Part B: retry, format check and stuck counter")
TRANSCRIPT_KEYS = ("task", "answer", "stop", "steps", "events", "usage", "gate", "yes_flag", "tools",
                   "system_files", "max_steps", "max_tokens", "answer_attempts", "messages")
# Key-shaped strings: a heuristic, so a match is a warning to act on, not proof.
KEY_RES = (re.compile(r"(?i)(api_key|_token|_secret)\s*=\s*\S{8,}"), re.compile(r"\bsk-[A-Za-z0-9]{20,}"))
CASE_SECONDS = 20  # an offline case that runs longer is a loop that never ends
with open(os.path.join("lab02", "partA", "answer.schema.json"), encoding="utf-8") as _f:
    SCHEMA = json.load(_f)

CASES = []


def case(name):
    def wrap(fn):
        CASES.append((name, fn))
        return fn
    return wrap


def label(name):
    return name.split(":", 1)[0]


def expect(cond, detail):
    if not cond:
        raise AssertionError(detail)


def reference():
    """The answer recomputed from the data: the source with the most failed password lines."""
    counts = {}
    with open(os.path.join(DATA, "auth.log"), encoding="utf-8") as f:
        for line in f:
            m = FAILED_RE.search(line)
            if m:
                counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    ip = max(counts, key=lambda k: (counts[k], k))
    return {"ip": ip, "count": counts[ip]}


def fresh(ask=lambda command: True, data_dir=DATA):
    """The run_shell tool list on a data directory, with every gate granted
    unless ask says otherwise."""
    tools.configure(data_dir=data_dir, ask=ask, guards=False)
    return tools.get(["run_shell"])


def probe_tools():
    """fresh() plus three checker-local tools: echo returns its text, boom
    raises an error, refuse raises tools.Denied."""
    def echo(text):
        return text

    def boom():
        raise ValueError("the disk is on fire")

    def refuse():
        raise tools.Denied("denied: not today")

    no_args = {"type": "object", "properties": {}, "additionalProperties": False}
    return fresh() + [
        {"name": "echo", "description": "Return the text unchanged.",
         "parameters": {"type": "object", "properties": {"text": {"type": "string"}},
                        "required": ["text"], "additionalProperties": False}, "fn": echo},
        {"name": "boom", "description": "Always fails.", "parameters": no_args, "fn": boom},
        {"name": "refuse", "description": "Always refused.", "parameters": no_args, "fn": refuse},
    ]


def shell(command):
    """One scripted step: a run_shell call."""
    return {"tool_calls": [{"name": "run_shell", "arguments": {"command": command}}]}


def run_loop(*args, **kwargs):
    """loop.run(), and the shape of what it returns."""
    r = loop.run(*args, **kwargs)
    keys = ("answer", "stop", "steps", "messages", "events", "usage")
    expect(isinstance(r, dict) and all(k in r for k in keys),
           f"run() must return a dict with the keys {', '.join(keys)}; got {r!r:.200}")
    return r


def tool_events(r):
    return [e for e in r["events"] if e.get("type") == "tool_call"]


def dispatch(call, tool_list):
    """loop.dispatch(), and the shape of what it returns."""
    result = loop.dispatch(call, tool_list)
    expect(isinstance(result, tuple) and len(result) == 3,
           f"dispatch() must return (result_text, ok, denied); got {result!r:.200}")
    expect(isinstance(result[0], str), f"the result must be text, got {type(result[0]).__name__}")
    return result


# ------------------------------------------------------------------ prompts


@case("prompts: build() names every tool and appends each extra file under its own heading")
def _():
    extra = {"name": "count_lines", "description": "Count the lines of one file.", "parameters": {}, "fn": None}
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for name, text in (("rules.md", "Answer in one sentence.\nCount with sort and uniq -c.\n"),
                           ("notes.md", "The log comes from web01.\n")):
            files.append(os.path.join(tmp, name))
            with open(files[-1], "w", encoding="utf-8") as f:
                f.write(text)
        prompt = prompts.build(tools.get(["run_shell"]) + [extra], extra_files=files)
        expect(isinstance(prompt, str), f"build() must return one string, got {type(prompt).__name__}")
        for tool in ("run_shell", "count_lines"):
            expect(tool in prompt, f"the prompt does not name the tool {tool}")
        for tool in tools.get(["run_shell"]) + [extra]:
            line = f"- {tool['name']}: {tool['description']}"
            expect(line in prompt.splitlines(), f"the prompt has no line {line[:50]!r}...; tool_block() writes one "
                                                "line per tool, '- <name>: <description>'")
        starts = []
        for path in files:
            heading = prompt.find(f"## {os.path.basename(path)}", starts[-1] + 1 if starts else 0)
            expect(heading >= 0, f"no '## {os.path.basename(path)}' heading in the prompt (files in the order given)")
            starts.append(heading)
        for i, path in enumerate(files):
            with open(path, encoding="utf-8") as f:
                text = f.read().strip()
            section = prompt[starts[i]:starts[i + 1] if i + 1 < len(starts) else len(prompt)]
            expect(text in section, f"the text of {os.path.basename(path)} is not under its heading")


@case("prompts: the prompt is stable and short")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "rules.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("Run wc -l first.\n")
        run_shell = tools.get(["run_shell"])
        first = prompts.build(run_shell, extra_files=[path])
        expect(prompts.build(run_shell, extra_files=[path]) == first,
               "two builds with the same tools and files differ; build() must return the same text every time")
    plain = prompts.build(run_shell)
    expect(TASK not in first and TASK not in plain, "the prompt contains the task; the task is the user message")
    expect(len(plain) < 3000, f"the prompt without extra files is {len(plain):,} characters; keep it under 3,000 "
                              "(it rides in every call)")


# ----------------------------------------------------------------- dispatch


@case("dispatch: a tool call runs and its result comes back as text")
def _():
    kit = probe_tools()
    text, ok, denied = dispatch({"id": "call_1", "name": "run_shell", "arguments": {"command": "wc -l auth.log"}}, kit)
    expect(ok and not denied, f"expected ok and not denied, got ok={ok!r}, denied={denied!r}: {text[:120]!r}")
    try:
        obj = json.loads(text)
    except ValueError:
        obj = None
    expect(isinstance(obj, dict), f"run_shell's dict should come back as JSON text (json.dumps), got {text[:120]!r}")
    expect(obj.get("exit_code") == 0 and "150" in str(obj.get("output")),
           f"wc -l auth.log should exit 0 and print 150, got {text[:120]!r}")
    text, ok, denied = dispatch({"id": "call_2", "name": "echo", "arguments": {"text": "plain text"}}, kit)
    expect(ok and not denied and text == "plain text",
           f"a tool that returns a string gives that string back unchanged, got {text!r}")


@case("dispatch: an unknown tool comes back as error text naming the available tools")
def _():
    kit = probe_tools()
    text, ok, denied = dispatch({"id": "call_1", "name": "read_file", "arguments": {"path": "auth.log"}}, kit)
    expect(not ok and not denied, f"an unknown tool is not ok and not denied, got ok={ok!r}, denied={denied!r}")
    expect(text.startswith("error:"), f"the text should start with 'error:', got {text[:120]!r}")
    missing = [name for name in ["read_file"] + [t["name"] for t in kit] if name not in text]
    expect(not missing, f"the text should name the tool asked for and every available tool; "
                        f"missing {', '.join(missing)} in {text[:160]!r}")


@case("dispatch: a tool exception is text for the model, not a crash")
def _():
    kit = probe_tools()
    text, ok, denied = dispatch({"id": "call_1", "name": "boom", "arguments": {}}, kit)
    expect(not ok and not denied, f"a failing tool is not ok and not denied, got ok={ok!r}, denied={denied!r}")
    expect(text.startswith("error:") and "ValueError" in text and "the disk is on fire" in text,
           f"expected 'error: ValueError: the disk is on fire', got {text[:120]!r}")
    text, ok, denied = dispatch({"id": "call_2", "name": "refuse", "arguments": {}}, kit)
    expect(not ok and denied and text == "denied: not today",
           f"tools.Denied gives (str(e), False, True), got ({text[:80]!r}, {ok!r}, {denied!r})")
    text, ok, denied = dispatch({"id": "call_3", "name": "run_shell", "arguments": {"cmd": "ls"}}, kit)
    expect(not ok and not denied and text.startswith("error:"),
           f"a call with the wrong argument name is error text, got ({text[:80]!r}, {ok!r}, {denied!r})")


# --------------------------------------------------------------------- loop


@case("loop: messages are system, user, assistant, tool, assistant and the tool_call_id matches")
def _():
    def answer(messages, tool_schemas, response_schema):
        last = messages[-1]
        expect(last.get("role") == "tool", f"the model should see the tool message last, got role {last.get('role')!r}")
        out = json.loads(last["content"])["output"].split()
        return {"text": json.dumps({"ip": out[-1], "count": int(out[0])})}

    r = run_loop(TASK, FakeModel([shell(PIPELINE), answer]), fresh(), max_steps=4)
    roles = [m.get("role") for m in r["messages"]]
    expect(roles == ["system", "user", "assistant", "tool", "assistant"], f"the message roles are {roles}")
    first, task, turn, result = r["messages"][:4]
    expect(first.get("content") == loop.SYSTEM, "with system=None, messages[0] must carry loop.SYSTEM")
    expect(task.get("content") == TASK, "messages[1] must be the task, verbatim")
    calls = turn.get("tool_calls")
    expect(calls and len(calls) == 1, f"the assistant message must carry its tool_calls, got {turn!r:.160}")
    expect(result.get("tool_call_id") == calls[0].get("id"),
           f"the tool message answers {result.get('tool_call_id')!r}, but the call's id is {calls[0].get('id')!r}")
    expect(r["stop"] == "answer", f"stop should be 'answer', got {r['stop']!r}")
    expect(client.parse_json(r["answer"] or "") == reference(), "the answer does not match the data")

    system, received = "The system prompt under test.", []

    def answer_now(messages, tool_schemas, response_schema):
        received.append(dict(messages[0]) if messages else {})
        return {"text": "done"}

    r = run_loop(TASK, FakeModel([answer_now]), fresh(), system=system, max_steps=2)
    expect(r["messages"][0].get("content") == system, "with system given, messages[0] must carry it, not loop.SYSTEM")
    expect(received and received[0].get("role") == "system" and received[0].get("content") == system,
           "the model must receive the system message first: send it the whole list")
    two = {"tool_calls": shell("wc -l auth.log")["tool_calls"] + shell("head -1 auth.log")["tool_calls"]}
    r = run_loop(TASK, FakeModel([two, {"text": "done"}]), fresh(), max_steps=3)
    roles = [m.get("role") for m in r["messages"]]
    expect(roles == ["system", "user", "assistant", "tool", "tool", "assistant"],
           f"a reply with two tool calls needs a tool message for each before the next request; the roles are {roles}")
    ids = [c.get("id") for c in r["messages"][2].get("tool_calls") or []]
    expect([m.get("tool_call_id") for m in r["messages"][3:5]] == ids and len(tool_events(r)) == 2,
           "each call of a reply runs in order: its tool message answers its id, and it gets its own tool_call event")


@case("loop: the thought is recorded beside the action")
def _():
    thought = "I will count failed logins per source."
    script = [{"text": thought, "tool_calls": shell("wc -l auth.log")["tool_calls"]}, {"text": "done"}]
    r = run_loop(TASK, FakeModel(script), fresh(), max_steps=4)
    events = r["events"]
    model = next((i for i, e in enumerate(events) if e.get("type") == "model" and e.get("step") == 1), None)
    tool = next((i for i, e in enumerate(events) if e.get("type") == "tool_call" and e.get("step") == 1), None)
    expect(model is not None and events[model].get("text") == thought,
           f"the model event of step 1 should carry the text {thought!r}")
    expect(tool is not None, "step 1 ran no tool call: a reply with a tool call is not the answer, even when it has "
                             "text; run its calls")
    expect(model < tool, "the model event must come before the tool event of the same step")
    turn = r["messages"][2] if len(r["messages"]) > 2 else {}
    expect(turn.get("content") == thought and turn.get("tool_calls"),
           "the assistant message must carry both the text and the tool call")


@case("loop: the answer stops the loop")
def _():
    fake = FakeModel([shell("wc -l auth.log"), {"text": "203.0.113.42, 31 times"}, shell("wc -l auth.log")])
    r = run_loop(TASK, fake, fresh(), max_steps=6)
    expect(r["stop"] == "answer", f"stop should be 'answer', got {r['stop']!r}")
    expect(fake.calls == 2, f"a reply with no tool call is the answer: expected 2 model calls, got {fake.calls}")
    expect(r["steps"] == 2 and r["answer"] == "203.0.113.42, 31 times",
           f"expected steps 2 and the reply text as the answer, got steps {r['steps']!r}, answer {r['answer']!r}")


@case("loop: the step cap")
def _():
    fake = FakeModel([shell("wc -l auth.log")])
    r = run_loop(TASK, fake, fresh(), max_steps=3)
    expect(fake.calls == 3, f"max_steps=3 allows exactly 3 model calls, got {fake.calls}")
    expect(r["stop"] == "step_cap" and r["answer"] is None and r["steps"] == 3,
           f"expected stop 'step_cap', answer None and steps 3, got {r['stop']!r}, {r['answer']!r}, {r['steps']!r}")
    expect(len(tool_events(r)) == 3, f"expected 3 tool events, got {len(tool_events(r))}")


@case("loop: usage is summed and one model event is emitted per call")
def _():
    fake = FakeModel([shell("wc -l auth.log"), {"text": "done"}])

    def counted(*args, **kwargs):  # FakeModel reports no usage; this wrapper reports 100 in, 10 out per call
        reply = fake(*args, **kwargs)
        reply["usage"] = {"input": 100, "output": 10}
        return reply

    r = run_loop(TASK, counted, fresh(), max_steps=4)
    expect(r["usage"] == {"input": 200, "output": 20, "calls": 2},
           f"expected usage {{'input': 200, 'output': 20, 'calls': 2}}, got {r['usage']!r}")
    models = [e for e in r["events"] if e.get("type") == "model"]
    expect([e.get("step") for e in models] == [1, 2], f"expected one model event per call, steps 1 and 2; "
                                                      f"got steps {[e.get('step') for e in models]}")
    expect(all(e.get("usage") == {"input": 100, "output": 10} for e in models),
           "each model event must carry that call's usage")


@case("loop: the three marker comments are in the body of run()")
def _():
    source = textwrap.dedent(inspect.getsource(loop.run))
    # Comment tokens only: a marker inside the docstring is text, not a comment.
    comments = [tok.string.lstrip("#").strip().lower()
                for tok in tokenize.generate_tokens(io.StringIO(source).readline) if tok.type == tokenize.COMMENT]
    missing = [m for m in MARKERS if not any(m[2:].lower() in c for c in comments)]
    expect(len(missing) < len(MARKERS), "no marker comment in the body of run()")
    expect(not missing, f"missing in the body of run(): {'; '.join(missing)}")
    code = loop.run.__code__
    expect("emit" in code.co_varnames + code.co_cellvars,
           "run() defines no emit() helper: write emit(event) inside run(), as its docstring says; lab 3's "
           "compaction hook, at the first marker, calls it")


# --------------------------------------------------------------------- gate


@case("gate: a refused command comes back as denied and the loop goes on")
def _():
    fake = FakeModel([shell(UNLISTED), {"text": "The command was refused, so I cannot tell."}])
    r = run_loop(TASK, fake, fresh(ask=lambda command: False), max_steps=3)
    ev = tool_events(r)
    expect(ev and ev[0].get("denied"), f"with the gate answering no, the tool event must be denied; got {ev!r:.200}")
    expect(str(ev[0].get("result", "")).startswith("denied:"),
           f"the result should start with 'denied:', got {ev[0].get('result')!r:.120}")
    expect(r["stop"] == "answer", f"the loop should go on to the answer after a refusal, got stop {r['stop']!r}")


# ---------------------------------------------------------------- run_shell


def sleepers():
    """The pids of processes whose whole command line is SLEEP."""
    try:
        return set(subprocess.run(["pgrep", "-fx", SLEEP.replace(".", "\\.")], capture_output=True,
                                  text=True).stdout.split())
    except FileNotFoundError:  # no pgrep: read /proc
        found = set()
        for pid in os.listdir("/proc") if os.path.isdir("/proc") else []:
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    if f.read() == SLEEP.replace(" ", "\0").encode() + b"\0":
                        found.add(pid)
            except OSError:
                pass
        return found


@case("run_shell: every command runs alone in the data directory with PAGER=cat")
def _():
    scratch = tempfile.mkdtemp(prefix="srt521-check-")
    try:
        data = os.path.join(scratch, "data")
        os.makedirs(os.path.join(data, "sub"))
        shutil.copy(os.path.join(DATA, "auth.log"), data)
        fresh(data_dir=data)
        here = os.path.realpath(data)
        r = tools.run_shell("pwd")
        expect(isinstance(r, dict) and r.get("exit_code") == 0, f"run_shell returns {{'exit_code', 'output'}}, got {r!r}")
        expect(os.path.realpath(r["output"].strip()) == here, f"pwd printed {r['output'].strip()!r}, not the data directory")
        expect(tools.run_shell("cd sub")["exit_code"] == 0, "cd sub failed in the data directory")
        r = tools.run_shell("pwd")
        expect(os.path.realpath(r["output"].strip()) == here, "a cd in one command carried over to the next")
        tools.run_shell("export SRT521_PROBE=1")
        r = tools.run_shell("printenv SRT521_PROBE")
        expect(r["exit_code"] == 1 and not r["output"].strip(), "a variable exported in one command carried over")
        r = tools.run_shell("printenv PAGER")
        expect(r["output"].strip() == "cat", f"PAGER should be cat, got {r['output'].strip()!r}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


@case("run_shell: no key in the child environment; files outside the data directory are refused, programs with slashes are not")
def _():
    asked = []
    fresh(ask=lambda command: asked.append(command) or True)
    saved = {name: os.environ.get(name) for name in ("SRT521_API_KEY", "HOME")}
    scratch = tempfile.mkdtemp(prefix="srt521-check-")
    try:
        os.environ["SRT521_API_KEY"] = "x"
        r = tools.run_shell("printenv SRT521_API_KEY")
        expect(r["exit_code"] == 1 and not r["output"].strip(), "SRT521_API_KEY reached the command's environment")
        if not os.path.isfile(os.path.expanduser("~/.bashrc")):  # no profile here: a scratch HOME that has one
            os.environ["HOME"] = scratch
            open(os.path.join(scratch, ".bashrc"), "w").close()
        del asked[:]
        for command in ("head ~/.bashrc", "cat /etc/passwd", "cat ../../agent/client.py", "ls ..",
                        "cat .*/.*/.bashrc", "cat $X$HOME/.bashrc"):
            try:
                tools.run_shell(command)
            except tools.Denied:
                continue
            raise AssertionError(f"{command!r} ran; an argument outside the data directory must be refused")
        expect(not asked, f"a command refused for its arguments must not reach the gate; the gate saw {asked}")
        grep = "/usr/bin/grep" if os.path.exists("/usr/bin/grep") else shutil.which("grep")
        for command in ("awk '/Failed password/ {print $11}' auth.log", "head -1 ./auth.log", f"{grep} -c x auth.log"):
            try:
                r = tools.run_shell(command)
            except tools.Denied as e:
                raise AssertionError(f"{command!r} was refused ({e}); it names nothing outside the data directory")
            expect(isinstance(r, dict) and "exit_code" in r, f"{command!r} did not run: {r!r:.120}")
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(scratch, ignore_errors=True)


@case("run_shell: a timeout is an observation, not a crash, and leaves no child running")
def _():
    before = sleepers()
    saved, tools.SHELL_TIMEOUT = tools.SHELL_TIMEOUT, 1
    started = time.monotonic()
    try:
        kit, command = fresh(), f"{SLEEP} | cat"
        try:
            text, ok, denied = dispatch({"id": "call_1", "name": "run_shell", "arguments": {"command": command}}, kit)
        except NotImplementedError:  # dispatch() not written yet: the given run_shell on its own
            try:
                text, ok, denied = f"no error: {tools.run_shell(command)!r}", True, False
            except tools.ToolError as e:
                text, ok, denied = f"error: {type(e).__name__}: {e}", False, False
    finally:
        tools.SHELL_TIMEOUT = saved
    elapsed = time.monotonic() - started
    expect(text.startswith("error: ToolError: command exceeded 1 seconds") and not ok and not denied,
           f"expected the text 'error: ToolError: command exceeded 1 seconds ...', got {text[:120]!r}")
    expect(elapsed < 2.9, f"the command ran {elapsed:.1f} seconds; the timeout should stop it after 1")
    left = sleepers() - before
    for _ in range(10):  # the killed processes may take a moment to go
        if not left:
            break
        time.sleep(0.1)
        left = sleepers() - before
    expect(not left, f"a '{SLEEP}' process survived the timeout (pid {', '.join(sorted(left))})")


# --------------------------------------------------------------- transcript


def load_transcript(path):
    expect(os.path.exists(path), f"{path} not found (the recorded run writes it with --transcript)")
    try:
        with open(path, encoding="utf-8") as f:
            t = json.load(f)
    except ValueError as e:
        raise AssertionError(f"{path} is not JSON: {e}") from None
    missing = [k for k in TRANSCRIPT_KEYS if not isinstance(t, dict) or k not in t]
    expect(not missing, f"{path} lacks the key(s) {', '.join(missing)}; python3 -m agent --transcript writes them")
    places = [(f"message {i}", m) for i, m in enumerate(t["messages"])]
    places += [(f"event {i}", e) for i, e in enumerate(t["events"])]
    places += [("the gate list", t["gate"]), ("the answer", t["answer"]), ("answer_attempts", t["answer_attempts"])]
    for name, item in places:
        text = json.dumps(item, ensure_ascii=False)
        if any(pattern.search(text) for pattern in KEY_RES):
            raise AssertionError(f"a key-shaped string in {name} of {path} (a heuristic match): "
                                 "rotate the key, rerun, do not commit")
    return t


def first_command(t):
    for e in t["events"]:
        if e.get("type") == "tool_call" and e.get("name") == "run_shell":
            return (e.get("arguments") or {}).get("command", "(none)")
    return "(no run_shell call)"


@case("transcript: lab02/partA/transcript.json is the recorded run")
def _():
    t = load_transcript(TRANSCRIPT)
    expect(t["stop"] == "answer", f"the recorded run must end with stop 'answer', got {t['stop']!r}")
    try:
        obj = client.parse_json(t["answer"] or "")
    except ValueError as e:
        raise AssertionError(f"the answer is not JSON: {e}") from None
    errors = client.validate(obj, SCHEMA)
    expect(not errors, f"the answer does not match answer.schema.json: {'; '.join(errors)}")
    expect(obj == reference(), f"the answer {json.dumps(obj)} does not match the data in {DATA}/auth.log")
    attempts = t["answer_attempts"] or []
    replies = [m for m in t["messages"] if m.get("role") == "assistant"]
    said = attempts[-1].get("text") if attempts else (replies[-1].get("content") if replies else "")
    try:
        consistent = client.parse_json(said or "") == obj
    except ValueError:
        consistent = False
    expect(consistent, "the answer is not the model's last reply; rerun the command instead of editing the file")
    ran = [e for e in t["events"] if e.get("type") == "tool_call" and e.get("name") == "run_shell" and e.get("ok")]
    expect(ran, "the transcript shows no run_shell call that ran")
    expect(any(e.get("type") == "model" for e in t["events"]), "the transcript shows no model event")
    expect(len(t["messages"]) > 2, "the transcript holds no conversation")
    built = prompts.build(tools.get(t["tools"]), extra_files=t["system_files"])
    system = t["messages"][0].get("content")
    expect(system != loop.SYSTEM or built == loop.SYSTEM,
           "messages[0] is loop.SYSTEM: run() ignored the system argument that python3 -m agent passed")
    expect(system == built, "messages[0]: the system prompt is not prompts.build() of agent/prompts.py as it is now; "
                            "rerun the command after your last change to prompts.py")
    expect(t["messages"][1].get("content") == t["task"], "messages[1] is not the task; the task goes in verbatim")
    gate = t["gate"] or []
    expect(gate, "no gate answer on camera: the gate list is empty"
                 + (" (the run used --yes)" if t["yes_flag"] else ""))
    expect(all(g.get("answer") in ("y", "n") for g in gate), "a gate entry carries no y or n answer")
    expect(t["yes_flag"] is False, "the run used --yes; the recorded run answers every gate on camera")
    return (f"{t['steps']} step(s), {len(tool_events(t))} tool call(s), {len(gate)} gate answer(s), "
            f"answer {json.dumps(obj)}")


@case("transcript: lab02/partA/transcript-rules.json carries rules.md in the system prompt")
def _():
    t = load_transcript(RULES_TRANSCRIPT)
    expect(t["system_files"] == [RULES], f"system_files is {t['system_files']}; "
                                         f"the second command adds --system-file {RULES}")
    expect(os.path.exists(RULES), f"{RULES} not found; the rule file is part of the work")
    with open(RULES, encoding="utf-8") as f:
        text = f.read()
    system = (t["messages"][0].get("content") or "") if t["messages"] else ""
    _, heading, tail = system.rpartition("## rules.md")
    expect(heading and tail.strip() == text.strip(),
           f"messages[0] does not end with the text of {RULES} under the heading ## rules.md; rerun the command "
           f"after your last change to {RULES}")
    built = prompts.build(tools.get(t["tools"]), extra_files=t["system_files"])
    expect(system == built, f"messages[0]: the system prompt is not prompts.build() of agent/prompts.py and {RULES} "
                            "as they are now; rerun the command after your last change to either")
    expect(t["stop"] == "answer", f"the rules run must end with stop 'answer', got {t['stop']!r}")
    expect(t["yes_flag"] is False, "the run used --yes; the recorded run answers every gate on camera")
    try:
        with open(TRANSCRIPT, encoding="utf-8") as f:
            before = first_command(json.load(f))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        before = f"({TRANSCRIPT} not readable)"
    return f"first command without the rule: {before}\nfirst command with the rule:    {first_command(t)}"


# --------------------------------------------------------------------- live


@case("live: your loop answers the task through the provider in agent/client.py")
def _():
    kit = fresh()
    r = run_loop(TASK, client.complete, kit, system=prompts.build(kit), max_steps=6)
    expect(r["stop"] == "answer", f"stop should be 'answer', got {r['stop']!r}")
    obj, attempts = client.finish_json(r["messages"], r["answer"], SCHEMA)
    expect(obj == reference(), f"the model's answer {json.dumps(obj)} does not match the data")
    commands = "; ".join(e["arguments"].get("command", "?") for e in tool_events(r)) or "(none)"
    return (f"{r['steps']} step(s), {len(attempts)} answer attempt(s), {r['usage']['input']:,} tokens in, "
            f"{r['usage']['output']:,} out; commands: {commands}")


# ------------------------------------------------------------------- runner


class CaseTimeout(BaseException):
    """Raised by the alarm; a BaseException, so a dispatch() that catches Exception cannot swallow it."""


def on_alarm(signum, frame):
    raise CaseTimeout()


def breakpoint_notes():
    """One note for every breakpoint() call in agent/*.py."""
    notes = []
    folder = os.path.join(ROOT, "agent")
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(folder, name), encoding="utf-8", errors="replace") as f:
            source = f.read()
        try:
            lines = sorted(node.lineno for node in ast.walk(ast.parse(source))
                           if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "breakpoint")
        except (SyntaxError, ValueError):  # a file that does not parse yet: read it line by line
            lines = [n for n, text in enumerate(source.splitlines(), 1) if re.match(r"\s*breakpoint\s*\(", text)]
        notes += [f"note: breakpoint() in agent/{name}, line {n}; remove it before the recorded run" for n in lines]
    return notes


def where(error):
    """Where an error came from: the innermost frame in agent/ and, when that
    is given code, the innermost frame of the modules you write."""
    agent = os.path.join(ROOT, "agent") + os.sep
    frames = [f for f in traceback.extract_tb(error.__traceback__) if os.path.abspath(f.filename).startswith(agent)]
    if not frames:
        return ""
    at = [f"agent/{os.path.basename(f.filename)}, line {f.lineno}, in {f.name}()" for f in frames]
    yours = [i for i, f in enumerate(frames) if os.path.basename(f.filename) in ("prompts.py", "loop.py", "context.py")]
    if yours and yours[-1] != len(frames) - 1:
        return f" ({at[-1]}; called from {at[yours[-1]]})"
    return f" ({at[-1]})"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="skip the transcript cases")
    mode.add_argument("--live", action="store_true", help="add the live case, which calls your provider")
    ap.add_argument("-k", action="append", default=[], metavar="LABEL",
                    help="run only the cases with this label, the word before the colon; repeatable")
    ap.add_argument("--debug", action="store_true",
                    help="let a breakpoint() in agent/ stop a case at a (Pdb) prompt, with no time limit")
    args = ap.parse_args()
    if args.debug:
        if BREAKPOINT_SETTING is None:
            os.environ.pop("PYTHONBREAKPOINT", None)
        else:
            os.environ["PYTHONBREAKPOINT"] = BREAKPOINT_SETTING

    skip = {"transcript", "live"} if args.offline else set() if args.live else {"live"}
    enabled = [(name, fn) for name, fn in CASES if label(name) not in skip]
    labels = list(dict.fromkeys(label(name) for name, _ in enabled))
    unknown = [k for k in args.k if k not in labels]
    if unknown:
        ap.error(f"no case labelled {', '.join(unknown)} in this run; the labels are {', '.join(labels)}")
    selected = [(name, fn) for name, fn in enabled if not args.k or label(name) in args.k]

    for note in breakpoint_notes():
        print(note)
    alarm = hasattr(signal, "SIGALRM")
    if alarm:
        signal.signal(signal.SIGALRM, on_alarm)
    passed = failed = 0
    for name, fn in selected:
        if alarm:
            signal.alarm(0 if label(name) == "live" or args.debug else CASE_SECONDS)
        try:
            detail = fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {name}\n      {e}")
        except CaseTimeout:
            failed += 1
            print(f"FAIL  {name}\n      the case did not finish in {CASE_SECONDS} seconds; is there a loop that never ends?")
        except (Exception, SystemExit) as e:  # a crash in your code is a failure, with where it happened
            failed += 1
            place = "" if isinstance(e, NotImplementedError) else where(e)
            print(f"FAIL  {name}\n      {type(e).__name__}: {e}{place}")
        else:
            passed += 1
            print(f"PASS  {name}")
            for line in (detail or "").splitlines():
                print(f"      {line}")
        finally:
            if alarm:
                signal.alarm(0)
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
