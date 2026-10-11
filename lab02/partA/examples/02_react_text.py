#!/usr/bin/env python3
"""Example 2: a ReAct loop in text mode, for any chat model.

    python3 lab02/partA/examples/02_react_text.py
    python3 lab02/partA/examples/02_react_text.py --parse < reply.txt

ReAct (reason, then act) is the pattern of the loop you write in
agent/loop.py: the model writes a thought, asks for one action, reads what
the action printed (the observation), and goes on until it can answer. Here
the action travels as plain text, so any chat model can play, even one
without tool calling: each reply is THOUGHT: and one sentence, then one
fenced block whose info string is srt521-action and whose body is one shell
command. One regular expression, printed at the start, finds the command; the
script runs it with subprocess in lab02/partA/data and sends the output back
as the next user message. A reply with no fenced block is the answer.

A reply whose only block has another name, ```bash for example, is refused
with a format error the model reads. mini-SWE-agent v2 renamed its own fence
for the same reason: a bash example quoted in a thought must never run.
--parse reads one reply from standard input and prints what the parser makes
of it, so you can try that case without a model.

It reads SRT521_API_BASE, SRT521_API_KEY (or OPENAI_API_KEY), SRT521_MODEL and
SRT521_TIMEOUT. Standard library only; it does not import agent/.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

API_BASE = os.environ.get("SRT521_API_BASE", "https://api.openai.com/v1")
API_KEY = os.environ.get("SRT521_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("SRT521_MODEL", "gpt-4o-mini")
TIMEOUT = float(os.environ.get("SRT521_TIMEOUT") or 60)
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
# The command's environment carries no keys, as in agent/tools.py.
CHILD_ENV = {k: v for k, v in os.environ.items() if not k.endswith(("_KEY", "_TOKEN", "_SECRET", "_PASSWORD"))}
ACTION_RE = re.compile(r"```srt521-action[ \t]*\n(.*?)\n```", re.DOTALL)
TASK = "Which source IP had the most failed SSH password attempts, and how many?"
SYSTEM = """You answer questions about the files in the current directory by running shell commands.
Start every reply with THOUGHT: and one sentence of reasoning, then give exactly one command in a
fenced block named srt521-action, like this:

THOUGHT: I need the format of the log before I count anything.

```srt521-action
head -3 auth.log
```

The output of the command comes back in the next message. When you know the answer, reply with
THOUGHT: and a JSON object such as {"ip": "192.0.2.1", "count": 3}, and no fenced block."""


def parse(reply):
    """("action", command), ("answer", reply) or ("refused", reason)."""
    actions = ACTION_RE.findall(reply)
    if len(actions) == 1:
        return "action", actions[0].strip()
    if actions:
        return "refused", f"{len(actions)} srt521-action blocks; send exactly one"
    fence = re.search(r"```(\S*)", reply)
    if fence:
        return "refused", f"a ```{fence.group(1)} block; the command goes in a ```srt521-action block"
    return "answer", reply


def ask(messages):
    """One chat request, with no tools field; returns the reply text."""
    body = json.dumps({"model": MODEL, "messages": messages}).encode("utf-8")
    request = urllib.request.Request(API_BASE.rstrip("/") + "/chat/completions", data=body,
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.load(response)["choices"][0]["message"]["content"] or ""


def main():
    if sys.argv[1:] == ["--parse"]:
        print("%s: %s" % parse(sys.stdin.read()))
        return
    print(f"action regex: {ACTION_RE.pattern}")
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": TASK}]
    for exchange in range(1, 7):
        reply = ask(messages)
        messages.append({"role": "assistant", "content": reply})
        print(f"\n--- exchange {exchange}\n{reply.strip()}")
        kind, value = parse(reply)
        if kind == "answer":
            print(f"\nANSWER {re.sub(r'^THOUGHT:.*', '', reply.strip()).strip() or reply.strip()}")
            return
        if kind == "refused":
            observation = f"FORMAT ERROR: the reply has {value}."
        else:
            try:
                done = subprocess.run(value, shell=True, cwd=DATA, env=CHILD_ENV, text=True, timeout=10,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                observation = f"exit code {done.returncode}\n{done.stdout}"
            except subprocess.TimeoutExpired:
                observation = "error: the command ran longer than 10 seconds"
        print(f"OBSERVATION {observation.strip()}")
        messages.append({"role": "user", "content": observation})
    print("\nno answer after 6 exchanges")


if __name__ == "__main__":
    main()
