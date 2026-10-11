"""The tools the loop can call, and the permission gate in front of the shell.

A tool is a dict: {"name", "description", "parameters", "fn"}. "parameters"
is the JSON schema the model sees; fn(**arguments) returns a string or a
JSON-serialisable object, and the loop turns it into the tool message.

Lab 2 part A ships one tool, run_shell, in confirm mode: every command is
shown to the human at the gate, ASK(command), and runs only after a yes.
Before the gate, an argument that names a file outside the data directory,
as written or once the shell has expanded it, is refused without asking.
The command then runs alone, in a fresh shell in the data directory, with a
timeout and an environment that carries no keys.
Part B adds the allowlist, so the gate asks only about commands it does not
know; lab 3 adds search_notes, lab 4 mcp_tools(), lab 5 guards.py.
"""
import fnmatch
import glob
import os
import re
import shlex
import signal
import subprocess

DATA_DIR = os.getcwd()
ALLOWLIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "allowlist.txt")
# A process safety net against a flood of output. From part B on, the clip in
# loop.dispatch() decides what the model sees.
MAX_CHARS = 20000
SHELL_TIMEOUT = 10
GUARDS = False  # lab 5 switches this on; nothing reads it before then
# The permission gate, set by configure(): ASK(command) returns True to run
# the command; False, or a string with the human's reason, refuses it.
ASK = None

# Set in every command's environment, as mini-SWE-agent does, so no pager
# waits for a key press.
ENV = {"PAGER": "cat", "MANPAGER": "cat", "LESS": "-R", "TERM": "dumb"}
# A variable whose name ends like this is left out of every command's environment.
SECRET_SUFFIXES = ("_KEY", "_TOKEN", "_SECRET", "_PASSWORD")


class ToolError(Exception):
    """The tool could not do what was asked; the loop reports it to the model."""


class Denied(ToolError):
    """The command was refused: by the containment check, the gate, the allowlist or the guards."""


def configure(data_dir=None, ask=None, guards=None):
    global DATA_DIR, ASK, GUARDS
    if data_dir is not None:
        DATA_DIR = os.path.abspath(data_dir)
    if ask is not None:
        ASK = ask
    if guards is not None:
        GUARDS = guards


# ---------------------------------------------------------------- allowlist
# Given now, used from part B on.

# Metacharacters the shell tool never accepts, whatever the command name:
# they chain, substitute or redirect, which the allowlist cannot see.
SHELL_META = (";", "&&", "||", "$(", "`", ">", "<", "&", "\n")


def load_allowlist(path=None):
    """Read allowlist.txt: 'allow NAME' and 'deny NAME' lines, '#' comments.
    Returns (allow, deny) as sets of command names."""
    allow, deny = set(), set()
    with open(path or ALLOWLIST_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            verb, _, name = line.partition(" ")
            if verb == "allow":
                allow.add(name.strip())
            elif verb == "deny":
                deny.add(name.strip())
    return allow, deny


# Part B: is_allowed(command, allow, deny) goes here.


# ---------------------------------------------------------------- run_shell


def arguments(command):
    """Every word after the first of each |-separated segment: the words that
    may name a file. The first word is the command, the allowlist's business."""
    words = []
    for segment in command.split("|"):
        try:
            parts = shlex.split(segment)
        except ValueError:  # an unbalanced quote: fall back to plain words
            parts = segment.split()
        words.extend(parts[1:])
    return words


# What the shell expands in a word after the containment check has read it:
# $NAME, ${...} and the special parameters $$, $!, $?, $#, $@, $* and $-.
EXPANSION = re.compile(r"\$(?:\{([^}]*)\}|(\w+)|[$!?#@*-])")
PATTERN = "*?["
GLOB_LIMIT = 1000  # a pattern that matches more paths than this counts as outside


def expanded(word, unknown="*"):
    """word as the shell will read it: ~ and the variables of the command's
    environment expanded (PWD is the data directory, where the command runs),
    and any other expansion, such as a shell variable like $PPID or a special
    parameter like $$, replaced by unknown."""
    env = dict(child_env(), PWD=os.path.realpath(DATA_DIR))

    def value(m):
        name = m.group(1) or m.group(2)
        return env.get(name, unknown) if name else unknown
    return os.path.expanduser(EXPANSION.sub(value, word))


def climb(path):
    """path with each component the shell can expand to .. written as ..:
    the shell matches .*, .? and .[.] against the entries . and .., which
    Python's glob never returns."""
    return "/".join(".." if part.startswith(".") and any(c in part for c in PATTERN)
                    and fnmatch.fnmatchcase("..", part) else part
                    for part in path.split("/"))


def outside(word):
    """True when word may name a path outside the data directory once the
    shell has expanded it. An expansion the check cannot know may become
    anything from nothing to a whole path, so the word is read twice, with
    each unknown expansion as * and as nothing. It is outside when either
    reading is: a ${...} with an operator; a path that climbs out with .. or
    with a pattern the shell expands to ..; a path outside that exists; or a
    pattern (*, ? or [...]) whose fixed start is a directory outside, or that
    matches a path outside. Words that name nothing on disk (search patterns,
    options, awk programs) pass."""
    root = os.path.realpath(DATA_DIR)

    def out(path):
        path = os.path.realpath(path)
        return not (path == root or path.startswith(root + os.sep))

    if any(not re.fullmatch(r"\w*", inner) for inner in re.findall(r"\$\{([^}]*)\}", word)):
        return True
    for reading in {expanded(word, "*"), expanded(word, "")}:
        path = os.path.join(root, reading)
        climbing = os.path.join(root, climb(reading))
        if ".." in climbing.split("/") and out(climbing):
            return True
        if out(path) and os.path.exists(path):
            return True
        if not any(c in reading for c in PATTERN):
            continue
        base, rest = ("/", reading[1:]) if reading.startswith("/") else (root, reading)
        parts = rest.split("/")
        fixed_parts = next(i for i, part in enumerate(parts) if any(c in part for c in PATTERN))
        fixed = os.path.join(base, *parts[:fixed_parts])
        if out(fixed) and os.path.isdir(fixed):
            return True  # every match would lie outside: no need to search
        for count, match in enumerate(glob.iglob(os.path.join(glob.escape(fixed), *parts[fixed_parts:]))):
            if out(match) or count >= GLOB_LIMIT:
                return True
    return False


def child_env():
    """The environment a command runs with: os.environ without keys, tokens,
    secrets or passwords, plus ENV."""
    env = {name: value for name, value in os.environ.items()
           if not name.upper().endswith(SECRET_SUFFIXES)}
    env.update(ENV)
    return env


def cut(text):
    if len(text) > MAX_CHARS:
        return text[:MAX_CHARS] + f"\n[truncated: {len(text)} characters in total]"
    return text


def run_shell(command):
    """Run one shell command in the data directory, after the containment
    check and the permission gate.

    Returns {"exit_code": int, "output": str}, stderr merged into output.
    Raises Denied when an argument names a file outside the data directory
    or the human does not answer yes, and ToolError when the command runs
    longer than SHELL_TIMEOUT seconds.
    """
    for word in arguments(command):
        if outside(word):
            raise Denied(f"denied: {word} is outside the data directory")
    # Lab 5: guards.gate() goes here
    # Part B: is_allowed() decides first, and the gate below asks only when it says "ask"
    answer = ASK(command) if ASK else False
    if answer is not True:
        reason = f": {answer.strip()}" if isinstance(answer, str) and answer.strip() else ""
        raise Denied(f"denied: permission was not given for {command}{reason}")
    exit_code, output = _run(command)
    return {"exit_code": exit_code, "output": cut(output)}


# Modelled on _run() in mini-SWE-agent v2.4.6 (MIT License, Copyright (c) 2025 Kilian A. Lieret and Carlos E. Jimenez):
# https://github.com/SWE-agent/mini-swe-agent/blob/v2.4.6/src/minisweagent/environments/local.py
def _run(command):
    process = subprocess.Popen(command, shell=True, cwd=DATA_DIR, text=True, encoding="utf-8",
                               errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True, env=child_env())
    try:
        output, _ = process.communicate(timeout=SHELL_TIMEOUT)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)  # the whole process group, so no child keeps running
        output, _ = process.communicate()
        raise ToolError(f"command exceeded {SHELL_TIMEOUT} seconds; "
                        f"partial output: {cut(output) or '(none)'}") from None
    return process.returncode, output


# -------------------------------------------------------------------- tools

TOOLS = {
    "run_shell": {
        "name": "run_shell",
        "description": ("Run one shell command in the data directory and return its exit code and "
                        "output. Each command runs on its own: a cd or a variable set in one command "
                        "is gone in the next. A refused command comes back as text starting with "
                        "denied: and the reason."),
        "parameters": {"type": "object",
                       "properties": {"command": {"type": "string",
                                                  "description": "The command line to run"}},
                       "required": ["command"],
                       "additionalProperties": False},
        "fn": run_shell,
    },
}


def get(names):
    """The tool dicts for a list of names, in that order."""
    missing = [n for n in names if n not in TOOLS]
    if missing:
        raise KeyError(f"unknown tool(s): {', '.join(missing)}; known: {', '.join(TOOLS)}")
    return [TOOLS[n] for n in names]


def register(tool):
    TOOLS[tool["name"]] = tool
    return tool
