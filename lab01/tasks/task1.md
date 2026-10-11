# Task 1 (agent alpha): web probes

You are alpha. Read `AGENTS.md` first if you have not. Work from `~/SRT521-2026/lab01/` and never change into `alpha/`.

## 1. Spec
Read `specs/web_probes.md` in full and implement it exactly. Read no other data file than `access.log`. Do not read `firewall.log`, `check.py`, or anything under `beta/`.

## 2. Files to produce
- `alpha/web_probes.py`: Python 3.11, standard library only, reads `access.log` from the current directory.
- `alpha/output.json`: the program's output.
Write only inside `alpha/` and `mailbox/`. Create `alpha/` if it is missing.

## 3. Run and check
From `lab01/`:
```
python3 alpha/web_probes.py > alpha/output.json
python3 check.py alpha/output.json
```
If the check prints FAIL, read the message, fix `alpha/web_probes.py`, and rerun until it prints PASS. Do not edit `check.py`, and do not import from it.

## 4. Done message
Only after the check passes, create `mailbox/task1-done.md` containing:
- the line `task 1 done`
- the path `alpha/output.json`
- the result of `python3 check.py alpha/output.json` (PASS)
- the five IPs in `top`, one per line

If you cannot make the check pass, still write `mailbox/task1-done.md` with the first line `task 1 FAILED`, the last check output, and what you tried. Beta reads it either way.

## 5. Boundaries
Never edit `beta/`, `specs/`, `tasks/`, `check.py`, `access.log`, `firewall.log`, or any file in `mailbox/` that you did not create. Never delete a mailbox file. Do not run git commands.

## 6. Stopping condition
Stop as soon as `mailbox/task1-done.md` is written. Do not start task 2. If any instruction here is missing or unclear, report what is missing and stop; do not invent requirements.
