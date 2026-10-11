# Lab 02 A — Building a Tool-Calling Security Agent

**Author:** Rabbi Muhammad Aman · **Course:** SRT521

## Version info

```
Fri Sep 25 23:30:47 EDT 2026
tmux 3.4
Python 3.12.3
b4ca96f Lab 02a plan
```

## Environment

Recorded on the host: Windows 11 (WSL Ubuntu). Multiplexer: tmux 3.4. Editor: nano. Coding agent in a pane: none.

## Provider

`SRT521_API_BASE`: https://generativelanguage.googleapis.com/v1beta/openai. Model: gemini-3.5-flash-lite. `SRT521_TIMEOUT`: 120.

Seconds per model call, about: 1 to 3 each . The `response_format` fallback, a `[schema] the provider refused response_format` line in the trace: did not fire.

## The recorded runs

`python3 lab02/partA/check.py` at the end of the recording: 17 passed, 0 failed.

| | First run, `transcript.json` | Rules run, `transcript-rules.json` |
|---|---|---|
| The commands the model chose, in order | 1. `ls -la`<br>2. `head -n 20 auth.log`<br>3. `python3 -c "
with open('auth.log') as f:
    for i in range(20):
        print(f.readline(), end='')
"`<br>4. `python3 -c "
from collections import Counter
import re

c = Counter()
with open('auth.log') as f:
    for line in f:
        if 'Failed password' in line:
            m = re.search(r'from (\S+) port', line)
            if m:
                c[m.group(1)] += 1

for ip, count in c.most_common(5):
    print(ip, count)
"` | 1. `wc -l auth.log` |
| Your answer at each gate, and the reason you typed after each `n` | y, n (yy), y, y | y |
| Steps and the stop reason | 5 step(s), answer | 2 step(s), answer |
| Tokens in and out, from `show.py` | 5,111 in, 248 out, 5 call(s) | 821 in, 56 out, 2 call(s) |

What the rule in `rules.md` changed, and what it left the same:
The rule changed the first command. Without it the model started with `ls -la`, with it model started `wc -l auth.log` as my rule asked.The final answer which is {"ip": "203.0.113.42", "count": 31} remained same. 
One thing the model or the harness did that you did not expect, with the trace line that shows it:
Rule 1 asks for one sentence of reasoning before every tool call, but gemini sent no text beside its tool calls. so the trace shows "[step 1] thought: (none from this provider)` on every step. Also the final answer was not schema-valid JSON, so --schema asked again: `[schema] schema-valid after 2 attempt(s)`.

## AI use

### Tools used, and how
The lab's agent was python -m agent with the model gemini-3.5-flash-lite.
### Prompts I wrote
- Task given to the lab's agent in both recorded runs: "Which source IP had the most failed SSH password attempts, and how many?"
- Extra rule given in the second run through `--system-file lab02/partA/rules.md`: "Before any other command, run wc -l on the log file and say how many lines it has.

### Results the AI produced
It gave me agent/prompts.py and agent/loop.py with fixed syntax error from a shell-scripting mistake. It also came up with the answer: answer: {"ip": "192.168.1.100", "count": 5}

### How the results went into the submission
I have a script that was recording all the command output that was needed for report. I copy the template and the script replace it with the answer and all the execute commands. 
