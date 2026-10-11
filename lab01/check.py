#!/usr/bin/env python3
"""Lab 1 checker, NAA variant: compares an agent's JSON output with the answer
computed from the data files.

    python3 lab01/check.py lab01/alpha/output.json              # task 1: web_probes
    python3 lab01/check.py --blocked lab01/beta/blocked.json    # task 2, first half: blocked_ports
    python3 lab01/check.py --report lab01/beta/report.json      # task 2, second half: the report

The reference is recomputed from lab01/access.log and lab01/firewall.log every
time. Students implement the specs without importing these reference functions.
Exit status 0 means the output matches.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ACCESS_RE = re.compile(r'^(\d+\.\d+\.\d+\.\d+) \S+ \S+ \[[^\]]+\] "(\S+) (\S+) [^"]*" (\d{3}) ')
BLOCK_RE = re.compile(r"\[UFW BLOCK\].*?\bSRC=(\d+\.\d+\.\d+\.\d+)\b.*?\bDPT=(\d+)\b")


def reference_web_probes(path):
    counts, paths = {}, {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = ACCESS_RE.match(line)
            if m and m.group(4) == "404":
                ip = m.group(1)
                counts[ip] = counts.get(ip, 0) + 1
                paths.setdefault(ip, set()).add(m.group(3))
    top = sorted(counts, key=lambda ip: (-counts[ip], ip))[:5]
    return {"top": [{"ip": ip, "count": counts[ip], "paths": sorted(paths[ip])} for ip in top]}


def reference_blocked_ports(path):
    counts, sources = {}, []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = BLOCK_RE.search(line)
            if not m:
                continue
            src, port = m.group(1), int(m.group(2))
            counts[port] = counts.get(port, 0) + 1
            if src not in sources:
                sources.append(src)
    ports = [{"port": p, "blocked": counts[p]} for p in sorted(counts, key=lambda p: (-counts[p], p))]
    return {"ports": ports, "sources": sources}


def reference_report(access_path, firewall_path):
    top = [entry["ip"] for entry in reference_web_probes(access_path)["top"]]
    blocked = reference_blocked_ports(firewall_path)
    seen = set(blocked["sources"])
    return {"block": [ip for ip in top if ip not in seen],
            "already_blocked": [ip for ip in top if ip in seen],
            "top_port": blocked["ports"][0]["port"]}


def diff(got, want, path="$"):
    """Human-readable differences between two JSON values."""
    problems = []
    if type(got) is not type(want):
        return [f"{path}: expected {type(want).__name__}, got {type(got).__name__}"]
    if isinstance(want, dict):
        for key in want:
            if key not in got:
                problems.append(f"{path}.{key}: missing")
            else:
                problems.extend(diff(got[key], want[key], f"{path}.{key}"))
        for key in got:
            if key not in want:
                problems.append(f"{path}.{key}: unexpected key")
    elif isinstance(want, list):
        if path == "$.sources" and got != want and sorted(map(str, got)) == sorted(map(str, want)):
            return [f"{path}: sources must follow first-appearance order"]
        if path == "$.ports" and got != want and all(isinstance(e, dict) for e in got) \
                and sorted(json.dumps(e, sort_keys=True) for e in got) == sorted(json.dumps(e, sort_keys=True) for e in want):
            return [f"{path}: ports must be sorted by blocked count, then port number"]
        if len(got) != len(want):
            problems.append(f"{path}: expected {len(want)} item(s), got {len(got)}")
        for i, (g, w) in enumerate(zip(got, want)):
            problems.extend(diff(g, w, f"{path}[{i}]"))
    elif got != want:
        problems.append(f"{path}: expected {want!r}, got {got!r}")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("output", help="the JSON file an agent's script produced")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--blocked", "--firewall", action="store_true", help="check blocked.json (the blocked_ports task)")
    mode.add_argument("--report", action="store_true", help="check report.json (the report task)")
    ap.add_argument("--data", help="data file for the web_probes or blocked_ports check (default: next to this script)")
    args = ap.parse_args()

    access = os.path.join(HERE, "access.log")
    firewall = os.path.join(HERE, "firewall.log")
    if args.report:
        want = reference_report(access, firewall)
    elif args.blocked:
        want = reference_blocked_ports(args.data or firewall)
    else:
        want = reference_web_probes(args.data or access)

    try:
        with open(args.output, encoding="utf-8") as f:
            got = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"FAIL: cannot read {args.output}: {e}")
        return 1

    problems = diff(got, want)
    if problems:
        print(f"FAIL: {len(problems)} difference(s) from the reference")
        for p in problems[:20]:
            print("  " + p)
        if len(problems) > 20:
            print(f"  ... and {len(problems) - 20} more")
        return 1
    print("PASS: output matches the reference")
    return 0


if __name__ == "__main__":
    sys.exit(main())
