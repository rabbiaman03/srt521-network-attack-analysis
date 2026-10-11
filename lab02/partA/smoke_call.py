#!/usr/bin/env python3
"""One structured call through agent/client.py. Run from the repository root:

    python3 lab02/partA/smoke_call.py

It asks the model for a JSON object matching lab02/partA/answer.schema.json
and prints the parsed object and how many attempts it took. It proves three
things at once: the provider settings work, complete() translates the reply,
and complete_json() enforces the schema. No tool is involved.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent import client  # noqa: E402

MESSAGES = [
    {"role": "system", "content": "Reply with one JSON object that matches the schema. No prose."},
    {"role": "user", "content": "Host 203.0.113.9 had 7 failed SSH password attempts, more than any other "
                                "source. Report the source and the count."},
]


def main():
    with open(os.path.join(ROOT, "lab02", "partA", "answer.schema.json"), encoding="utf-8") as f:
        schema = json.load(f)
    print(f"provider: {client.API_BASE}  model: {client.MODEL}")
    obj, attempts = client.complete_json(MESSAGES, schema)
    print(json.dumps(obj))
    print(f"schema-valid after {len(attempts)} attempt(s)")
    for i, a in enumerate(attempts[:-1], 1):
        print(f"  attempt {i} failed: {'; '.join(a['errors'])}")
    if any(a.get("schema_fallback") for a in attempts):
        print("the provider refused response_format; the reply text was checked against the schema instead")


if __name__ == "__main__":
    main()
