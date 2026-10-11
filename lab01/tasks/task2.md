# Task 2 (agent beta): blocked ports, then the report

You are beta. Read `AGENTS.md` first if you have not. Work from `~/SRT521-2026/lab01/` and never change into `beta/`. Task 2 has two stages. `Continue task 2` means: re-read this file, check what is already done, and finish the rest without redoing completed stages or deleting mailbox messages.

## Stage A: blocked ports (independent of alpha, start immediately)

### 1. Spec
Read `specs/blocked_ports.md` in full and implement it exactly. Read no other data file than `firewall.log`.

### 2. Files
- `beta/blocked_ports.py`: Python 3.11, standard library only.
- `beta/blocked.json`: its output.

### 3. Run and check
From `lab01/`:
```
python3 beta/blocked_ports.py > beta/blocked.json
python3 check.py --blocked beta/blocked.json
```
Fix and rerun until PASS. Do not edit or import `check.py`.

## Stage B: the report (needs alpha)

### 4. Wait for alpha
The dependency is `mailbox/task1-done.md`. If it does not exist yet, poll for it every 15 seconds, in batches of at most 60 seconds (for example a shell loop of 4 checks with `sleep 15`), up to five batches. A shell-tool timeout counts as a batch toward that five-minute budget. Do not read `alpha/` while waiting.

**Fallback A (message never comes):** after five batches, write `mailbox/task2-waiting.md` naming the missing dependency (`mailbox/task1-done.md`) and what you finished (blocked.json and its check result), then stop. Do not write `task2-done.md`.

### 5. Validate alpha's result
When the message exists, read it. If its first line is `task 1 FAILED`, or `alpha/output.json` is missing, is not valid JSON, or has no `top` list, that is **Fallback B**: keep `beta/blocked.*` as they are, write `mailbox/task2-done.md` with the first line `task 2 partial`, state the input failure (which file, what is wrong) and the blocked.json check result, and stop. Do not create or repair alpha's files.

### 6. Spec and files
Otherwise read `specs/report.md` in full and implement it. Read only `alpha/output.json` and `beta/blocked.json`; do not read `access.log` or `firewall.log` again.
- `beta/make_report.py`: Python 3.11, standard library only.
- `beta/report.json`: its output.

### 7. Run and check
From `lab01/`:
```
python3 beta/make_report.py > beta/report.json
python3 check.py --report beta/report.json
```
Fix `beta/make_report.py` until PASS. If the check fails only because alpha's output is wrong, do not fix alpha's file: treat it as Fallback B and report it.

## Done message
Create `mailbox/task2-done.md` containing: the line `task 2 done`, the paths of blocked.json and report.json, the PASS results of both checks, and the contents of `block`, `already_blocked` and `top_port`. (Variants: `task 2 partial` under Fallback B.)

## Boundaries
Write only inside `beta/` and the named `mailbox/` files. Never edit `alpha/`, `specs/`, `tasks/`, `check.py`, the logs, or mailbox files you did not create. Never delete a mailbox file. No git commands.

## Stopping condition
Stop when `mailbox/task2-done.md` (or `mailbox/task2-waiting.md`) is written. Do not start any other task. If an instruction is missing, report it and stop.
