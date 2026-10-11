"""The agent loop: a ReAct loop, the part of the agent you write.

ReAct (reason, then act) is the pattern the loop follows: the model reads the
conversation, states its reasoning and asks for an action (a tool call), the
harness runs the tool and appends the result (the observation), and the model
is asked again, until it answers without a tool call or a limit stops the run.

run() is the loop and dispatch() runs one tool call; both are yours, from the
contracts in their docstrings. SYSTEM, RESULT_CHARS and schemas() are given.
run() takes the model function as an argument, so the checker drives it with
agent.fake.FakeModel and python3 -m agent passes client.complete.
"""
import json

from . import tools as tools_mod

SYSTEM = "You are a careful assistant inside a small harness; use the tools you are given and answer when you know."
# How much of each tool result a tool_call event keeps: more than run_shell's
# 20,000-character cut and the JSON around it, so the trace can count the
# whole tool message the model reads.
RESULT_CHARS = 24000
# Test 01 task 2: the user message that follows the first answer
CHECK = "Check your answer against the tool results, then give your final answer."


def schemas(tools):
    """The tool definitions the model sees: name, description and parameters, without the Python function."""
    return [{"name": t["name"], "description": t["description"], "parameters": t["parameters"]}
            for t in tools]

def clip(text):
    """Task 1: Clip output longer than 3,000 chars to head (2,000) and tail (800)."""
    if len(text) > 3000:
        elided = len(text) - 2000 - 800
        return text[:2000] + f"\n[... {elided:,} characters elided ...]\n" + text[-800:]
    return text

def dispatch(call, tools):
    """Run one tool call and return (result_text, ok, denied).

    call is one entry of a reply's "tool_calls": {"id", "name", "arguments"},
    arguments already a dict. tools is the list of tool dicts the loop was given.

    - No tool in tools has call["name"]: return
      ("error: unknown tool NAME; available tools: a, b", False, False), with
      the name the model asked for and the names in tools, so the model can
      pick a real one.
    - Otherwise call the tool's "fn" with the arguments as keyword arguments:
      fn(**call["arguments"]).
    - tools_mod.Denied raised (the command was refused): return
      (str(e), False, True).
    - Any other exception e: return (f"error: {type(e).__name__}: {e}", False, False).
    - A result that is not a string is json.dumps()ed (run_shell returns a
      dict); return (result, True, False).

    Errors are text for the model, never exceptions: the model reads the
    reason and can take another route. Part B adds an argument check and the
    clip of long results here.
    """
    tool = next((t for t in tools if t["name"] == call["name"]), None)
    if tool is None:
        names = ", ".join(t["name"] for t in tools)
        return f"error: unknown tool {call['name']}; available tools: {names}", False, False
    try:
        result = tool["fn"](**call["arguments"])
    except tools_mod.Denied as e:
        return str(e), False, True
    except Exception as e:
        return f"error: {type(e).__name__}: {e}", False, False
    if isinstance(result, dict) and "output" in result and isinstance(result["output"], str):
        result = dict(result)
        result["output"] = clip(result["output"])
    elif isinstance(result, str):
        result = clip(result)
    if not isinstance(result, str):
        result = json.dumps(result)
    return result, True, False


def run(task, complete, tools, *, system=None, max_steps=8, max_tokens=None, on_event=None,
        compact=None, max_messages=None):
    """Run the loop on one task and return what happened.

    task          the question, sent verbatim as the user message
    complete      the model function: complete(messages, tools=...) returns
                  {"text", "tool_calls", "usage": {"input", "output"}, ...}
                  (client.complete, or a FakeModel in the checker)
    tools         the tool dicts from tools.get()
    system        the system prompt (python3 -m agent passes prompts.build());
                  None means SYSTEM
    max_steps     the step cap: at most this many model calls
    on_event      a function called with each event as it happens (the trace
                  and the transcript of python3 -m agent); may be None
    max_tokens, compact, max_messages
                  accepted and ignored in part A: part B uses max_tokens,
                  lab 3 compact and max_messages

    The contract:

    - messages starts as [{"role": "system", "content": system or SYSTEM},
      {"role": "user", "content": task}].
    - The totals start as used = {"input": 0, "output": 0, "calls": 0}.
    - For each step from 1 to max_steps: reply = complete(messages,
      tools=schemas(tools)); emit {"type": "model", "step": step,
      "text": reply["text"], "tool_calls": len(reply["tool_calls"]),
      "usage": reply["usage"]} and add that usage and one call to the
      totals; append {"role": "assistant", "content": reply["text"],
      "tool_calls": reply["tool_calls"]}.
    - A reply with no tool calls is the answer: return
      finish(reply["text"], "answer", step).
    - Otherwise, for each call in the reply: result, ok, denied =
      dispatch(call, tools); append {"role": "tool", "tool_call_id":
      call["id"], "content": result}; emit {"type": "tool_call", "step": step,
      "id": call["id"], "name": call["name"], "arguments": call["arguments"],
      "ok": ok, "denied": denied, "result": result[:RESULT_CHARS]}.
    - When the loop runs out: return finish(None, "step_cap", max_steps).

    emit() and finish() are two small helpers you write inside run(), before
    the loop, so they reach the events list, the messages and the totals:
    emit(event) appends event to the events list and calls on_event(event)
    when on_event is given; finish(answer, stop, steps) returns {"answer",
    "stop", "steps", "messages", "events", "usage"}, with usage the totals:
    the input and output tokens summed over every call, and the number of
    calls. Every event goes through emit(); lab 3's compaction hook calls it
    too.

    Three comment lines go in the body of run(), at the places they name,
    because part B and lab 3 add code there: "# Lab 3: compaction hook" as the
    first line inside the for step loop; "# Part B: budget check" before the
    model call; "# Part B: retry, format check and stuck counter" at the model
    call.
    """
    messages = [{"role": "system", "content": system or SYSTEM},
                {"role": "user", "content": task}]
    used = {"input": 0, "output": 0, "calls": 0}
    events = []
    checked = False  # Test 01 task 2: the check message goes out only once

    def emit(event):
        events.append(event)
        if on_event:
            on_event(event)

    def finish(answer, stop, steps):
        return {"answer": answer, "stop": stop, "steps": steps, "messages": messages,
                "events": events, "usage": dict(used)}

    for step in range(1, max_steps + 1):
        # Lab 3: compaction hook
        # Part B: budget check
	# Part B Task 2: context window keeping only the 3 most recent tool messages
        tool_indices = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
        if len(tool_indices) > 3:
            older = tool_indices[:-3]
            elided = len(older)
            chars = sum(len(messages[i]["content"]) for i in older)
            emit({"type": "window", "step": step, "elided": elided, "chars": chars})
            kept = set(tool_indices[-3:])
            sent_messages = []
            for i, m in enumerate(messages):
                if m.get("role") == "tool" and i not in kept:
                    c_len = len(m["content"])
                    sent_messages.append({
                        "role": "tool",
                        "tool_call_id": m.get("tool_call_id"),
                        "content": f"[earlier tool result elided: {c_len:,} chars]"
                    })
                else:
                    sent_messages.append(m)
        else:
            sent_messages = list(messages)

        # Part B: retry, format check and stuck counter
        reply = complete(sent_messages, tools=schemas(tools))
        usage = reply["usage"]
        emit({"type": "model", "step": step, "text": reply["text"],
              "tool_calls": len(reply["tool_calls"]), "usage": usage})
        used["input"] += usage.get("input", 0)
        used["output"] += usage.get("output", 0)
        used["calls"] += 1
        messages.append({"role": "assistant", "content": reply["text"],
                         "tool_calls": reply["tool_calls"]})
        if not reply["tool_calls"]:
            # Test 01 task 2: the first answer gets the check message and one more model call
            if not checked and step < max_steps:
                checked = True
                messages.append({"role": "user", "content": CHECK})
                continue
            return finish(reply["text"], "answer", step)

        for call in reply["tool_calls"]:
            result, ok, denied = dispatch(call, tools)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
            emit({"type": "tool_call", "step": step, "id": call["id"], "name": call["name"],
                  "arguments": call["arguments"], "ok": ok, "denied": denied,
                  "result": result[:RESULT_CHARS]})
            # Test 01 task 1: a refusal with the reason "stop" ends the run at this step
            stop_text = f"denied: permission was not given for {call['arguments'].get('command')}: stop"
            if denied and result == stop_text:
                return finish(None, "stopped", step)
    return finish(None, "step_cap", max_steps)