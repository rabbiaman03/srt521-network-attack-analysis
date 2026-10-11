#!/usr/bin/env python3
"""Warm-up: count the lines of auth.log by kind and print a small table.

    python3 lab02/partA/warmup.py

The script ships with two bugs. The handout walks you through both.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "data", "auth.log")
KINDS = ("Failed password", "Accepted publickey", "Accepted password")

counts = {kind: 0 for kind in KINDS + ("other",)}
with open(LOG, encoding="utf-8") as f:
    for line in f:
        kind = "other"
        for name in KINDS:
            if name in line:
                kind = name
        counts[kind] += 1

for kind, n in counts.items():
    print(f"{kind:<20}{n:>5}")
print(f"{'total':<20}{sum(counts.values()):>5}")
