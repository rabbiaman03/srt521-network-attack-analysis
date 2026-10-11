"""Try the clip and the window without a provider. From the repository root:

    python3 lab02/partB/try_context.py

A scripted model asks four times for a tool that prints 10,000 characters, then answers.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent import fake, loop  # noqa: E402


def big():
    return {"exit_code": 0, "output": "H" * 2000 + "M" * 7200 + "T" * 800}


TOOLS = [{"name": "big", "description": "Print 10,000 characters.",
          "parameters": {"type": "object", "properties": {}}, "fn": big}]
sent = []  # the tool messages the model read in each call


def model(messages, tools, response_schema):
    sent.append([m["content"] for m in messages if m["role"] == "tool"])
    return {"text": "done"} if len(sent) == 5 else {"tool_calls": [{"name": "big"}]}


result = loop.run("Try the context controls.", fake.FakeModel([model]), TOOLS, max_steps=8)
for n, contents in enumerate(sent, 1):
    print(f"call {n} read tool results of", [len(c) for c in contents], "characters")
for e in result["events"]:
    if e["type"] == "window":
        print("window event:", e)
kept = [len(m["content"]) for m in result["messages"] if m["role"] == "tool"]
print("the loop's own list keeps", kept)
clipped = [line for line in json.loads(sent[1][0])["output"].splitlines() if "elided" in line]
print("call 2 read the clip line:", clipped[0] if clipped else "(none)")
output = json.loads(sent[1][0])["output"]
print("call 2 clip starts and ends with:", output[:1], output[-1:])
print("call 5 read the first result as:", sent[4][0][:60])
