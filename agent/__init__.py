"""SRT521 agent harness: the package python3 -m agent runs.

The lab 2 modules:

__main__.py    the command line: flags, the gate on this terminal, the trace, the transcript
client.py      the model call; the only file that knows the provider
tools.py       run_shell: the containment check, the permission gate, the subprocess
fake.py        FakeModel and NotesFake, scripted stand-ins for the model the checkers use
prompts.py     the system prompt, written in part A
loop.py        the ReAct loop: call, dispatch, append, stop; written in part A
context.py     part B: the clip of long observations and the window over old results
allowlist.txt  part B: the commands the gate runs without asking, and the ones it refuses

Labs 3 to 5 add retrieval and memory (lab 3), MCP tools (lab 4) and guards (lab 5).

Run from the repository root: python3 -m agent --help
"""
