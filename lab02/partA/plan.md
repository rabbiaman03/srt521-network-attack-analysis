# Lab 02a plan

## System prompt rules
1. One sentence of reasoning before every tool call, saying what the call should show.
2. Exactly one tool call per step.
3. Every command starts in the data directory; cd and export do not persist.
4. head before counting; at most 20 lines printed; aggregate with sort and uniq -c.
5. On "error:" or "denied:", read the reason and try another route.
6. Answer with no tool call when done; JSON only when a schema was given.

## Loop
- Messages: system, user, then per step assistant (with tool_calls) + one tool message per call (matching tool_call_id), final assistant answer.
- Stop reasons: "answer" (reply with no tool calls) or "step_cap" (max_steps model calls used).
- Every event goes through emit(); finish() returns answer, stop, steps, messages, events, usage.

## Expected commands on auth.log and gate answers
- head -5 auth.log -> y (reads only the data file, shows the line format).
- grep "Failed password" auth.log | grep -oE "from [0-9.]+" | sort | uniq -c | sort -rn | head -3 -> y.
- wc -l auth.log (run 2) -> y.
- Anything reading outside data/ (cat /etc/passwd, ~/.bashrc, ../agent) -> n "reads outside the data directory".
- Anything that writes or deletes (rm, >, tee) -> n "the task only needs reading".

## rules.md
Before any other command, run wc -l on the log file and say how many lines it has.
