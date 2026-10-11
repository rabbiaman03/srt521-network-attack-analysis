# Lab 01 — Coordinating Two AI Agents for Log Analysis

**Author:** Rabbi Muhammad Aman · **Course:** SRT521 · **Date:** 2026-09-19

## Overview
Two LLM coding agents ran side by side in a terminal multiplexer (herdr), each with its own task brief. They coordinated only through files in a shared `mailbox/` directory:

| Agent | Model | Task | Output |
|---|---|---|---|
| **alpha** | Claude | Find the top web-probing IPs in `access.log` | [`alpha/web_probes.py`](alpha/web_probes.py) → [`alpha/output.json`](alpha/output.json) |
| **beta** | Gemini | (A) Analyze blocked ports in `firewall.log`; (B) wait for alpha, then merge both results into a report | [`beta/blocked_ports.py`](beta/blocked_ports.py), [`beta/make_report.py`](beta/make_report.py) → [`beta/report.json`](beta/report.json) |

My job was the orchestration: I wrote the [plan](PLAN.md) and the task briefs ([task1](tasks/task1.md), [task2](tasks/task2.md)), set the boundaries each agent had to respect, and designed the hand-off and fallback logic.

## Environment
```
Sat Sep 19 12:40:13 EDT 2026
herdr 0.9.1
Python 3.12.3
992a8ea Lab 01 work
```
Host: Windows 11 with WSL Ubuntu. Multiplexer: herdr. Agents: alpha = Claude, beta = Gemini.

## Results

| | alpha, task 1 | beta, task 2 |
|---|---|---|
| Prompts given | `start task 1` | `Start task 2`, then approved each permission request |
| `check.py` validation | `output.json`: **PASS** | `blocked.json`: **PASS** · `report.json`: **PASS** |
| Clarifying questions | none | none (asked for 7 permissions) |
| Hand-off message | [`task1-done.md`](mailbox/task1-done.md) | [`task2-done.md`](mailbox/task2-done.md) |
| Time from start to done | 20 s | 1 min 10 s |

## Hand-off design
- Beta starts its independent stage (blocked ports) immediately, then polls for `mailbox/task1-done.md` every 15 s, for at most five 60-second batches.
- **Fallback A:** if alpha's message never arrives, beta writes `task2-waiting.md` and stops.
- **Fallback B:** if alpha reports failure or its JSON is invalid, beta keeps its own results and writes `task 2 partial`.

## Reflection
The plan held. Alpha (Claude) finished first without needing any permissions. Beta (Gemini) asked for seven permission confirmations before writing files. When `task1-done.md` appeared, beta was still working through its permission prompts on stage A. Once they were approved, it picked up alpha's result and finished stage B, so neither fallback ran.

**Next time:** I will paste each spec's exact JSON key names and value types into the task brief instead of pointing the agent at `specs/*.md`. That removes the risk of an agent misreading the schema.

## Run the checks
```bash
cd lab01
python3 check.py alpha/output.json
python3 check.py --blocked beta/blocked.json
python3 check.py --report beta/report.json
```

## AI use
Alpha (Claude) and beta (Gemini) wrote all of the scripts, the JSON outputs and the mailbox messages, which are committed unedited. Claude Code helped me draft the plan and task briefs before the run. The results and reflection are my own account.
