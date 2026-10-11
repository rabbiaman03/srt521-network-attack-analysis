# Lab 02b plan

## Task 1, the clip
- Where: agent/loop.py, function `dispatch()`, right after my line `return f"error: {type(e).__name__}: {e}", False, False`.
- Why there: at that point the tool returned normally (the `error:` and `denied:` paths have already returned, so they are never clipped), and the result is still a dict, so I can clip only its `output` field before `json.dumps` turns it into valid JSON text. In `run()` it would already be a JSON string.
- Rule: a normal result over 3,000 characters becomes its first 2,000 characters, the line `[... N characters elided ...]`, and its last 800; for run_shell only the `output` field is clipped, `exit_code` stays, and the message stays valid JSON. `error:` and `denied:` texts are not clipped.
- Trace after the change: the grep tool_call line drops from about 10,000 chars to about 2,900, and show.py prints the `characters elided` line under it. The try script prints `[... 7,200 characters elided ...]` and `H T`.

## Task 2, the window
- Where: agent/loop.py, function `run()`, right after my line `for step in range(1, max_steps + 1):` (below the `# Part B: budget check` comment).
- Why there: the next line is the model call, so the copy is rebuilt before every call and the window event goes out before it; the model gets the copy while `messages` keeps every clipped result for the transcript.
- Rule: the model gets a copy of the list where only the three newest tool messages keep their content; older ones become `[earlier tool result elided: N chars]` with the same tool_call_id. My own list keeps every clipped result.
- Trace after the change: `[step N] window: {"elided": ..., "chars": ...}` before the model call, from the fifth call on if the model runs one command per step. The try script shows call 5 reading `[41, 2867, 2867, 2867]`.

## Tokens
- Before: input tokens jump after the grep step (about 10,000 characters, roughly 2,500 tokens) and stay high, because every later call resends that result.
- After: the jump is about a third as large (about 2,900 characters), and from the fifth call the oldest result costs only a short placeholder, so input tokens stop growing with it.

## What the window might hide
- The first result to drop out is the grep listing, then the Failed password count. If the model did not restate that count in its own text, its final answer may miss it or repeat the command. Confirmed if the trace shows a window event and then a repeated count command or a wrong first count; disproved if all four counts match `grep -c` with no repeated command.
