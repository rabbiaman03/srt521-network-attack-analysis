#!/usr/bin/env python3
"""Example 3: one tool call by hand, the loop you are about to write, unrolled.

    python3 lab02/partA/examples/03_tool_call_by_hand.py

A tool call is the model asking the program to run a function for it: the
request offers a list of tools (a name, a description and a JSON schema of
the arguments), and the reply names one of them and gives the arguments,
instead of or beside its text. This script makes the two requests of a
two-step run by hand, with one tool, run_shell:

1. Request 1 sends the system prompt, the task and the tool list. The reply
   carries a thought (its text, when the provider sends one: THOUGHT) and a
   tool call (ACTION). The arguments arrive as a string of JSON, and
   json.loads() turns them into a dict.
2. The script runs the command with subprocess in lab02/partA/data
   (OBSERVATION: the exit code and the first lines of output), appends the
   assistant turn and a tool message that answers the call by its id, and
   sends the whole list again: request 2.
3. The reply to request 2 has no tool call, so its text is the ANSWER.

In the agent, agent/client.py's complete() does the translation of step 1,
and run() in agent/loop.py, which you write, repeats steps 1 and 2 until a
reply comes without a tool call.

It reads SRT521_API_BASE, SRT521_API_KEY (or OPENAI_API_KEY), SRT521_MODEL and
SRT521_TIMEOUT. Standard library only; it does not import agent/.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

API_BASE = os.environ.get("SRT521_API_BASE", "https://api.openai.com/v1")
API_KEY = os.environ.get("SRT521_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("SRT521_MODEL", "gpt-4o-mini")
TIMEOUT = float(os.environ.get("SRT521_TIMEOUT") or 60)
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
# The command's environment carries no keys, as in agent/tools.py.
CHILD_ENV = {k: v for k, v in os.environ.items() if not k.endswith(("_KEY", "_TOKEN", "_SECRET", "_PASSWORD"))}
TASK = "Which source IP had the most failed SSH password attempts, and how many?"
SYSTEM = ("You answer questions about the files in the data directory with the run_shell tool. "
          "Before the tool call, say in one sentence what it should show. When you know the answer, "
          'reply with a JSON object such as {"ip": "192.0.2.1", "count": 3} and no tool call.')
RUN_SHELL = {"type": "function",
             "function": {"name": "run_shell",
                          "description": "Run one shell command in the data directory and return its exit code and output.",
                          "parameters": {"type": "object",
                                         "properties": {"command": {"type": "string", "description": "The command line to run"}},
                                         "required": ["command"]}}}


def post(messages):
    """One request with the tool list; returns the reply message and the usage."""
    body = json.dumps({"model": MODEL, "messages": messages, "tools": [RUN_SHELL]}).encode("utf-8")
    request = urllib.request.Request(API_BASE.rstrip("/") + "/chat/completions", data=body,
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            reply = json.load(response)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} from the provider: {e.read(300).decode('utf-8', 'replace')}")
    usage = reply.get("usage") or {}
    return reply["choices"][0]["message"], f"{usage.get('prompt_tokens') or 0:,} in, {usage.get('completion_tokens') or 0:,} out"


messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": TASK}]
print("request 1: 2 messages (system, user) and the run_shell tool")
reply, usage1 = post(messages)
if reply.get("content"):
    print(f"THOUGHT {reply['content']}")
calls = reply.get("tool_calls") or []
if not calls:
    sys.exit(f"ANSWER {reply.get('content')}\n(the model answered without a tool call; run it again)")
call = calls[0]  # one call answered here; the loop you write answers every call in a reply
arguments = call["function"]["arguments"]
print(f"ACTION {call['function']['name']} {arguments}")
print(f"       the arguments arrived as a string of JSON ({type(arguments).__name__}); json.loads() made a dict of them")
command = json.loads(arguments)["command"]
done = subprocess.run(command, shell=True, cwd=DATA, env=CHILD_ENV, text=True, timeout=10,
                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
lines = done.stdout.splitlines()
print(f"OBSERVATION exit {done.returncode}, {len(lines)} line(s)")
for line in lines[:5]:
    print(f"       {line}")

messages.append({"role": "assistant", "content": reply.get("content"),
                 "tool_calls": [{"id": call["id"], "type": "function",
                                 "function": {"name": call["function"]["name"], "arguments": arguments}}]})
messages.append({"role": "tool", "tool_call_id": call["id"],
                 "content": json.dumps({"exit_code": done.returncode, "output": done.stdout})})
print("request 2: 4 messages (system, user, the assistant turn with its tool call, the tool message)")
reply, usage2 = post(messages)
if reply.get("tool_calls"):
    print(f"ACTION {reply['tool_calls'][0]['function']['name']} {reply['tool_calls'][0]['function']['arguments']}")
    print("       the model wants another step; run() in agent/loop.py keeps going until a reply has no tool call")
else:
    print(f"ANSWER {reply.get('content')}")
print(f"usage: request 1 {usage1}; request 2 {usage2} (request 2 sent the whole conversation again)")
