#!/usr/bin/env python3
"""Example 1: one request to the model, one reply, and what it cost.

    python3 lab02/partA/examples/01_call.py

A model call is one HTTP POST. The request carries the model name and the
conversation so far, a list of messages; the reply carries the model's text
and the usage, the number of tokens (pieces of words, about four characters
each) the provider read and wrote. Nothing is remembered between two calls:
the next request has to send the whole conversation again.

It reads the four settings agent/client.py reads: SRT521_API_BASE,
SRT521_API_KEY (or OPENAI_API_KEY), SRT521_MODEL and SRT521_TIMEOUT.
Standard library only; it does not import agent/.
"""
import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = os.environ.get("SRT521_API_BASE", "https://api.openai.com/v1")
API_KEY = os.environ.get("SRT521_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("SRT521_MODEL", "gpt-4o-mini")
TIMEOUT = float(os.environ.get("SRT521_TIMEOUT") or 60)

body = {"model": MODEL,
        "messages": [{"role": "system", "content": "You are a concise assistant. Answer in one sentence."},
                     {"role": "user", "content": "What does an SSH server log when someone types a wrong password?"}]}
request = urllib.request.Request(API_BASE.rstrip("/") + "/chat/completions",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {API_KEY}"})
print(f"POST {request.full_url}  model: {MODEL}")
try:
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        reply = json.load(response)
except urllib.error.HTTPError as e:
    sys.exit(f"HTTP {e.code} from the provider: {e.read(300).decode('utf-8', 'replace')}")
except (urllib.error.URLError, OSError) as e:
    sys.exit(f"no answer from {API_BASE}: {getattr(e, 'reason', e)}")

print(reply["choices"][0]["message"]["content"])
usage = reply.get("usage") or {}
print(f"usage: {usage.get('prompt_tokens') or 0:,} in, {usage.get('completion_tokens') or 0:,} out")
