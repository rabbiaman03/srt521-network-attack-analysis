# Task 2 spec, first half: blocked_ports.py

Input: `firewall.log` in `lab01/`, a synthetic sample of the kernel log of a host running UFW: blocked connection attempts, a few allowed ones and unrelated kernel lines. Read no other data file.

Program: `beta/blocked_ports.py`, Python 3.11, standard library only. It runs from `lab01/` as `python3 beta/blocked_ports.py > beta/blocked.json` and reads `firewall.log` from the current directory.

Output: one JSON object.

```json
{"ports": [{"port": N, "blocked": M}], "sources": ["..."]}
```

- A line counts when it contains `[UFW BLOCK]`. `[UFW ALLOW]`, `[UFW AUDIT]` and every other kernel line do not.
- `ports` holds every destination port (`DPT=`) that appears on at least one blocked line, as an integer, with `blocked`, the number of such lines for that port; sorted by `blocked` descending, ties broken by port number ascending.
- `sources` holds the distinct source addresses (`SRC=`) of the blocked lines, in the order of their first appearance in the file.

Check, from `lab01/`: `python3 check.py --blocked beta/blocked.json`.
