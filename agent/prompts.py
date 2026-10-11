"""The system prompt: the instructions the model reads before the task.

The system prompt is the first message of the conversation, the one with the
role "system". The loop resends the whole message list in every call, so the
system prompt rides in every request: it is the part of the context that
stays the same from the first call to the last, which is why it is built once
per run and kept short. The task is the second message, the user message,
and is never part of the system prompt.

build() puts the prompt together from four parts:

    ROLE           who the model is and what it works on
    tool_block()   one line per tool the loop offers
    RULES          how the model must work
    extra_block()  the text of each file given with --system-file

TEMPLATE and render() are given. ROLE, RULES, tool_block(), extra_block() and
build() are yours; the contracts are in the comments and docstrings below.
Check your work with python3 -m agent --show-prompt --data lab02/partA/data,
which prints the prompt build() returns, and python3 lab02/partA/check.py -k prompts.
"""
import os

# The layout of the prompt. render() fills {role}, {tools}, {rules} and
# {extra}; {extra} comes last, so the text of a --system-file ends the prompt.
TEMPLATE = """{role}

## Tools

{tools}

## Rules

{rules}{extra}"""

# Who the model is and what it works on, in one or two sentences of your own.
ROLE = ("You are a security log analyst working inside a small agent harness. "
        "You answer questions about the log files in the data directory by running shell commands.")

# Six rules in your own words, one per line:
# 1. one sentence of reasoning before every tool call, saying what the call should show;
# 2. one tool call per step;
# 3. changes to the directory or the environment do not persist from one command
#    to the next, and every command starts in the data directory;
# 4. look before you count: inspect a file with head before writing a pipeline over
#    it, never print more than 20 lines of a file at once, aggregate with sort and uniq -c;
# 5. a result starting "error:" or "denied:" means read the reason and take another route;
# 6. when the answer is ready, reply with no tool call, and with JSON only when a
#    schema was given.
RULES = """1. Before every tool call, write one sentence of reasoning that says what the call should show.
2. Ask for exactly one tool call per step.
3. Every command starts fresh in the data directory; a cd or an export does not carry over to the next command.
4. Look before you count: inspect a file with head first, never print more than 20 lines at once, and aggregate with sort and uniq -c.
5. If a result starts with "error:" or "denied:", read the reason and take a different route.
6. When you have the answer, reply without a tool call, and use JSON only when a schema was given."""


class _Strict(dict):
    def __missing__(self, name):
        raise KeyError(f"missing variable: {name}")


def render(template, **values):
    """Fill the {name} fields of template from values.

    A field with no value raises KeyError("missing variable: NAME") instead of
    leaving a hole in the prompt: the lab's version of the strict template
    variables in mini-SWE-agent (Jinja's StrictUndefined).
    """
    return template.format_map(_Strict(values))


def tool_block(tools):
    """One line per tool, in the order given: "- <name>: <description>".

    tools is a list of tool dicts from tools.get(), for example
    tools.get(["run_shell"]); the lines are joined with newlines.
    """
    return "\n".join(f"- {t['name']}: {t['description']}" for t in tools)


def extra_block(extra_files):
    """The text of each file in extra_files, each under its own heading.

    For each path, in the order given: a blank line, the heading
    "## <file name>" (the file's base name, for example "## rules.md"), a
    blank line, then the file's text verbatim (read as UTF-8). No files: "".
    """
    parts = []
    for path in extra_files or ():
        with open(path, encoding="utf-8") as f:
            text = f.read()
        parts.append(f"\n\n## {os.path.basename(path)}\n\n{text}")
    return "".join(parts)


def build(tools, extra_files=()):
    """The system prompt for one run: TEMPLATE rendered with ROLE,
    tool_block(tools), RULES and extra_block(extra_files).

    One string, built once when the run starts and never changed during it.
    The task is not in it. Without extra files it stays under 3,000
    characters (about 750 tokens), because it rides in every call.
    python3 -m agent calls prompts.build(tool_list, extra_files=args.system_file)
    and passes the result to loop.run(..., system=...).
    """
    return render(TEMPLATE, role=ROLE, tools=tool_block(tools), rules=RULES,
                  extra=extra_block(extra_files))
