# Lab 02 B — Context Management: Clipping and Windowing Tool Output

**Author:** Rabbi Muhammad Aman · **Course:** SRT521

## Version info

```
Wed Oct  7 04:09:16 EDT 2026
tmux 3.4
Python 3.12.3
71acaee Lab 02b plan
```

## Environment

Recorded on the host: Windows 11 (WSL Ubuntu-24.04). Multiplexer: tmux 3.4. Editor: nano. Coding agent in a pane: none.

## Provider

`SRT521_API_BASE`: https://generativelanguage.googleapis.com/v1beta/openai. Model: gemini-3.5-flash-lite. `SRT521_TIMEOUT`: 120.

I did not install the catch-up package. `agent/client.py` keeps the Gemini `thought_signature` adaptation from part A, committed before part A's recording.

## Where the changes went

| | Task 1, the clip | Task 2, the window |
|---|---|---|
| The file and function you changed | `agent/loop.py`, dispatch() | `agent/loop.py`, run() |
| The line your change follows | `return f'error: {type(e).__name__}: {e}', False, False` (the except Exception return) | `for step in range(1, max_steps + 1):` (below the # Part B: budget check comment) |
| Why there, and not in another place | The tool has returned normally there, so error: and denied: texts are never clipped, and the result is still a dict, so only output is clipped before json.dumps keeps it valid JSON. In run() it would already be a JSON string. | The next line is the model call, so the copy is rebuilt and the window event emitted before every call. The model gets the copy while messages keeps every clipped result for the transcript. |
| Lines you added or changed, about | about 14 (the clip() helper and 6 lines in dispatch) | about 22, plus the complete() call changed to send the copy |

What you read in your own code to find these places: The dispatch() docstring (Part B adds ... the clip of long results here), the fn(**call['arguments']) call, the json.dumps line, the complete(messages, ...) call in run(), and the marker comments.

## The two runs

`python3 lab02/partA/check.py --offline` at the end of the recording: 15 passed, 0 failed.

| | Before, `transcript-before.json` | After, `transcript-after.json` |
|---|---|---|
| The commands the model chose, in order | 1. `grep "Failed password" auth.log`<br>2. `grep -c "Failed password" auth.log`<br>3. `grep -c "Accepted publickey" auth.log`<br>4. `grep -c "Accepted password" auth.log`<br>5. `grep -c "Connection closed" auth.log` | 1. `grep "Failed password" auth.log`<br>2. `grep -c "Failed password" auth.log`<br>3. `grep -c "Accepted publickey" auth.log`<br>4. `grep -c "Accepted password" auth.log`<br>5. `grep -c "Connection closed" auth.log` |
| Steps and the stop reason | 6 step(s), answer | 6 step(s), answer |
| Input tokens at each step, from `show.py` | step 1: 391, step 2: 6,049, step 3: 6,105, step 4: 6,161, step 5: 6,216, step 6: 6,270 | step 1: 391, step 2: 1,900, step 3: 1,956, step 4: 2,012, step 5: 610, step 6: 659 |
| Total tokens in and out | 31,192 in, 171 out, 6 call(s) | 7,528 in, 151 out, 6 call(s) |
| Characters in the serialized tool message for the `grep` listing, from the trace | 10,772 chars (step 1, `grep "Failed password" auth.log`) | 2,893 chars (step 1, `grep "Failed password" auth.log`) |
| `window` events: at which steps, and what they left out | none | step 5: 1 result(s), 2,893 chars<br>step 6: 2 result(s), 2,928 chars |

What the clip hid, and whether the model needed any of it. 

In the after run the `grep` listing at step 1 was clipped: the tool message is 2,893 characters instead of 10,772 in the before run, and the line `[... 7,840 characters elided ...]` replaced the middle of the listing (show.py prints it under that observation). The model kept the first 2,000 and the last 800 characters. It did not need the hidden lines: the four counts came from separate `grep -c` commands, not from the listing.

What the window left out that the model still needed, and what the model did about it (the trace lines that show it). 

The window first left results out before step 5: `[step 5] window: {"elided": 1, "chars": 2893}`; `[step 6] window: {"elided": 2, "chars": 2928}`. By the last call it had hidden `grep "Failed password" auth.log`, `grep -c "Failed password" auth.log`. The model did not run any command again after the window. The final answer is missing or wrong for Failed password, whose count result the window had hidden: the model needed it and had not restated it. 

The four counts each run reported, and whether they match the four manual `grep -c` checks in the handout:

The manual checks give Failed password 102; Accepted publickey 33; Accepted password 11; Connection closed 1. The before run reported Failed password 102; Accepted publickey 33; Accepted password 11; Connection closed 1. All four match the manual `grep -c` checks. The after run reported Failed password 34; Accepted publickey 33; Accepted password 11; Connection closed 1. These do not match the manual checks: Failed password.

## AI use

### Tools used, and how
I used Claude Code in the Claude desktop app (Code tab), model Claude Opus 5.5, in a separate window before the recording; it was not on camera and did not run in a pane. It explained the part B handout, copied `try_context.py` from the handout, drafted `plan.md` (including the four where/why lines, written from my finished code), wrote the setup, rehearsal and recording command list, and wrote `make_report_b.py`.

### Prompts I wrote
1. *"In Python, how do I truncate a string longer than 3,000 characters to keep the first 2,000 and last 800 characters, calculate the omitted length, and format the omitted number with thousands commas (e.g., 7,200) surrounded by newlines?"*
2. *"I have a tool function that might return either a string or a dict with an 'output' field. How can I safely clip only the 'output' field if it is a dict, preserve other keys like 'exit_code', and return valid JSON?"*
3. *"Given a list of message dicts with role and content, how can I find all tool messages, identify all except the 3 most recent, sum the character count of their content, and build a new list with replacement placeholders without modifying the original dicts in the master list?"*

### Results the AI produced
- Claude Code: an explanation of the lab; the plan skeleton and later the four where/why lines; the command list; `make_report_b.py`; plain-language steps for each change and Python building blocks (slicing, `f"{n:,}"`, `isinstance`, `dict()` copy); a review of my loop.py that found the missing `def clip` and the model call still sending `messages` instead of the windowed copy. It declined to write the clip and window code.

### How the results went into the submission
- `agent/loop.py`: I built `clip()` and the clip lines in `dispatch()`, and the window in `run()`, from the patterns above, fixed the two bugs Claude Code explained, and typed both changes on camera.
- `lab02/partB/plan.md`: Claude Code's draft, including the where/why lines, checked against my file.
- `lab02/partB/README.md`: generated by `make_report_b.py` from my recorded transcripts; the AI-use section is my own writing.
- `try_context.py`: the handout's script, unchanged. The transcripts are my recorded runs.
- Checked with `try_context.py` (`[41, 2867, 2867, 2867]` and the window event) and `check.py --offline` (15 passed).
