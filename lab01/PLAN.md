# Lab 1 plan

## 1. Roles
- alpha: <Claude Code, version> in herdr pane "alpha", directory `~/SRT521-2026/lab01/`. Runs task 1 (`tasks/task1.md`).
- beta: <agent, version> in pane "beta", same directory. Runs task 2 (`tasks/task2.md`).
- shell: third pane, me: watch, read mailbox, run checks. I type nothing else into agents.

## 2. Order
1. `Start task 1` into alpha.
2. While alpha works, `Start task 2` into beta. Beta does stage A (blocked ports) independently, then waits for alpha.
3. Beta stage B (report) depends on `mailbox/task1-done.md`.

## 3. Hand-off (`mailbox/`)
- `task1-done.md`: written by alpha after `check.py alpha/output.json` passes (or with `task 1 FAILED`). Contains status, output path, check result, the five IPs.
- `task2-done.md`: written by beta after both checks pass (or `task 2 partial`). Contains paths, check results, block / already_blocked / top_port.
- `task2-waiting.md`: written by beta only if alpha's message never arrives.

## 4. Fallback
Beta polls every 15 s, batches of 60 s, five batches max. If no `task1-done.md`, beta writes `task2-waiting.md` and stops; I check alpha's pane, and once `task1-done.md` exists I type `Continue task 2` once. If alpha's JSON is missing/invalid, beta keeps its blocked result and writes `task2-done.md` as `task 2 partial`.

## 5. Checks
From `lab01/`: `python3 check.py alpha/output.json`, `python3 check.py --blocked beta/blocked.json`, `python3 check.py --report beta/report.json`. Pass = each prints PASS, exit 0. Outputs and messages are left as the agents wrote them.
