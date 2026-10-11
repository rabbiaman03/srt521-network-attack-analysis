# Lab 1 report

Student: Rabbi Muhammad Aman, section NAA

## Version block

Copy the output of the four commands as the recording shows it (a command may print more than one line):

```
<date>
Sat Sep 19 12:40:13 EDT 2026
<herdr --version, tmux -V, or screen --version>
herdr 0.9.1
<python3 --version>
Python 3.12.3
<git log --oneline -1>
992a8ea (HEAD -> main, origin/main) Lab 01 work
```

## Recording

Recording submitted to the instructor (not public).

Recorded on the host: <Windows 11>. Multiplexer: <herdr 0.8>. Agents: alpha = <claude>, beta = <gemini>.

## Results

| | alpha, task 1 | beta, task 2 |
|---|---|---|
| Prompts and permission responses, every one (each prompt five words or fewer) | `start task 1` | `Start task 2`, then "Y" to all permission to do task 2 |

| `check.py` results | output.json: PASS | blocked.json: pass; report.json: pass |
| Questions it asked before doing |none |none but ask 7 permissions |
| Messages it wrote to `mailbox/` | task1-done.md|task2-done.md |
| Elapsed time from Start to done (or stopped without done) |20s |1m10s |
## Reflection

150 to 250 words, answering with specifics from your session:

1. Where your plan held and where it broke: what each agent did that its task file did not foresee, and what you changed in the files between the rehearsal and the recorded run.
It did not break anywhere. My alpha which was claude ai agent did not ask for any permission and did it first. My gemini, meanwhile asked for permissions prompt which I just di "Yes,Commit".
2. How the hand-off went: when `task1-done.md` appeared, what beta was doing at that moment, and whether the fallback ran.
when my task1-done.md was done. I was checking if task2 was breaking anything or not. But task2 was not done and it was asking for permissions. It asked 7 permissions which I approved. Then after sometimes task2 was also done. When I found both tasks were done in mailbox, I confirmed tasks were completed. 
3. One thing you will change in your task files or your plan for the next lab.
Next time I will paste the spec's exact JSON key names and value types directly into the next brief, instead of pointing the agent at specs/web_probes.md and trusting it to interept them.
## AI use
### Tools used, and how
I used alpha as claude and gemini as beta. I run them in my host machine using ubuntu (wsl) cmd.
### Prompts you wrote
start task1 in claude and start task2 in gemini,
### Results the AI produced
Alpha created web_probes.py and output.json. beta created blocked_ports.py, blocked.json,make_report.py and report.json and mailbox messages. 
### How the results went into the submission
I checked the mailbox and can see both tasks were finished and saw tasks completion message. 
