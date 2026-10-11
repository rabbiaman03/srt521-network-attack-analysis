"""The model call. This is the only file that knows which provider you use.

Everything above this file speaks one neutral format.

Messages, a list of dicts:

    {"role": "system",    "content": str}
    {"role": "user",      "content": str}
    {"role": "assistant", "content": str, "tool_calls": [ToolCall]}   # tool_calls may be []
    {"role": "tool",      "tool_call_id": str, "content": str}

    ToolCall = {"id": str, "name": str, "arguments": dict}

Tools, a list of dicts:

    {"name": str, "description": str, "parameters": <JSON schema of type object>}

complete(messages, tools=None, response_schema=None) returns:

    {"text": str,
     "tool_calls": [ToolCall],
     "stop": "end" | "tool_calls" | "length" | "other",
     "usage": {"input": int, "output": int}}

complete() translates: neutral messages in, provider request out, provider
reply in, neutral reply out. When the provider cannot parse a tool call's
arguments as JSON, the raw string goes under the key "_raw" so the loop can
tell the model what went wrong instead of crashing.

response_schema asks the provider for JSON that matches a schema (the
response_format field). Some providers refuse that field with HTTP 400;
complete() then sends the same request again without it and adds
"schema_fallback": True to the reply, and complete_json() and finish_json()
check the reply text against the schema themselves.

This reference implementation speaks the OpenAI-compatible chat completions
shape over plain HTTPS with the standard library, because many providers
offer that endpoint. Configure it with four environment variables:

    SRT521_API_BASE   default https://api.openai.com/v1
    SRT521_API_KEY    falls back to OPENAI_API_KEY
    SRT521_MODEL      default gpt-4o-mini
    SRT521_TIMEOUT    seconds to wait for one reply, default 60 (a local model may need 300)

Nothing else in the harness reads those variables.
"""
import itertools
import json
import os
import re
import urllib.error
import urllib.request

API_BASE = os.environ.get("SRT521_API_BASE", "https://api.openai.com/v1")
API_KEY = os.environ.get("SRT521_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("SRT521_MODEL", "gpt-4o-mini")
TIMEOUT_SECONDS = float(os.environ.get("SRT521_TIMEOUT") or 60)
# Ids for the tool calls of a provider that sends none, unique for the whole
# run, so every tool message answers exactly one call.
CALL_IDS = itertools.count(1)


class ProviderError(Exception):
    """The provider answered with an error or did not answer. status is the
    HTTP status code when there was one, otherwise None."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class SchemaError(Exception):
    """The model never produced JSON that matched the schema."""

    def __init__(self, attempts):
        super().__init__(f"no schema-valid reply after {len(attempts)} attempt(s)")
        self.attempts = attempts


# ----------------------------------------------------------------- complete


def complete(messages, tools=None, response_schema=None):
    body = {"model": MODEL, "messages": [_to_provider(m) for m in messages]}
    if tools:
        body["tools"] = [{"type": "function",
                          "function": {"name": t["name"],
                                       "description": t["description"],
                                       "parameters": t["parameters"]}}
                         for t in tools]
    if response_schema:
        body["response_format"] = {"type": "json_schema",
                                   "json_schema": {"name": "reply", "schema": response_schema}}
    fallback = False
    try:
        data = _post("/chat/completions", body)
    except ProviderError as e:
        if e.status != 400 or "response_format" not in body:
            raise
        # The provider refused response_format: ask again without it; the
        # callers check the text against the schema.
        del body["response_format"]
        data = _post("/chat/completions", body)
        fallback = True
    choices = data.get("choices") if isinstance(data, dict) else None
    if not choices:
        raise ProviderError(f"no reply in the answer from {API_BASE}: {json.dumps(data)[:300]}")
    choice = choices[0]
    message = choice.get("message") or {}
    calls = []
    for tc in message.get("tool_calls") or []:
        raw = tc.get("function", {}).get("arguments") or "{}"
        try:
            args = json.loads(raw)
            if not isinstance(args, dict):
                args = {"_raw": raw}
        except json.JSONDecodeError:
            args = {"_raw": raw}
        call = {"id": tc.get("id") or f"call_{next(CALL_IDS)}",
                "name": tc.get("function", {}).get("name", ""),
                "arguments": args}
        # Gemini adaptation: keep the thought_signature Gemini puts in
        # extra_content, so _to_provider() can send it back unchanged.
        if tc.get("extra_content"):
            call["extra_content"] = tc["extra_content"]
        calls.append(call)
    stop = {"stop": "end", "tool_calls": "tool_calls", "length": "length"}.get(
        choice.get("finish_reason"), "other")
    usage = data.get("usage") or {}
    reply = {"text": message.get("content") or "",
             "tool_calls": calls,
             "stop": "tool_calls" if calls else stop,
             "usage": {"input": usage.get("prompt_tokens") or 0,
                       "output": usage.get("completion_tokens") or 0}}
    if fallback:
        reply["schema_fallback"] = True
    return reply


def _to_provider(m):
    if m["role"] == "assistant":
        out = {"role": "assistant", "content": m.get("content") or None}
        if m.get("tool_calls"):
            out["tool_calls"] = []
            for c in m["tool_calls"]:
                tc = {"id": c["id"], "type": "function",
                      "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}}
                if c.get("extra_content"):  # Gemini adaptation: return the thought_signature
                    tc["extra_content"] = c["extra_content"]
                out["tool_calls"].append(tc)
        return out
    if m["role"] == "tool":
        return {"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]}
    return {"role": m["role"], "content": m["content"]}


def _post(path, body):
    req = urllib.request.Request(API_BASE.rstrip("/") + path,
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {API_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read(300).decode("utf-8", "replace")
        raise ProviderError(f"HTTP {e.code} from {API_BASE}: {detail}", status=e.code) from None
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", e)
        if isinstance(e, TimeoutError) or isinstance(reason, TimeoutError):
            raise ProviderError(f"no answer from {API_BASE} within {TIMEOUT_SECONDS:g} seconds; "
                                "a slow or local model needs a larger SRT521_TIMEOUT") from None
        raise ProviderError(f"no answer from {API_BASE}: {reason}") from None
    except ValueError as e:  # the body was not JSON
        raise ProviderError(f"the answer from {API_BASE} is not JSON: {e}") from None


# ------------------------------------------------------ schema validation

_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def validate(instance, schema, path="$"):
    """Check instance against a JSON schema. Returns a list of error strings,
    empty when the instance is valid.

    Supports the subset the labs need: type, properties, required, items,
    enum, minimum, maximum, additionalProperties false. Anything else in the
    schema is ignored, not rejected.
    """
    errors = []
    kind = schema.get("type")
    if kind:
        if kind == "integer":
            ok = isinstance(instance, int) and not isinstance(instance, bool)
        elif kind == "number":
            ok = isinstance(instance, (int, float)) and not isinstance(instance, bool)
        else:
            ok = isinstance(instance, _TYPES.get(kind, object))
        if not ok:
            return [f"{path}: expected {kind}, got {type(instance).__name__}"]
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} is below the minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} is above the maximum {schema['maximum']}")
    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}.{key}: missing")
        for key, sub in props.items():
            if key in instance:
                errors.extend(validate(instance[key], sub, f"{path}.{key}"))
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errors.append(f"{path}.{key}: not allowed")
    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            errors.extend(validate(item, schema["items"], f"{path}[{i}]"))
    return errors


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json(text):
    """Find the JSON object in a model reply, tolerating code fences and
    prose around it. Raises ValueError when there is none."""
    cleaned = _FENCE.sub("", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in the reply")
    try:
        return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON: {e.msg} at position {e.pos}") from None


def complete_json(messages, schema, complete=None, retries=2):
    """Call the model until its reply validates against schema.

    Returns (object, attempts). attempts is a list of {"text", "errors"} for
    every reply, so a transcript can show the retry; an attempt whose reply
    came through the response_format fallback also carries
    "schema_fallback": True. Raises SchemaError when the last retry still
    fails. Pass complete= to use a different model function, for example a
    FakeModel in a test.
    """
    call = complete or globals()["complete"]
    msgs = list(messages)
    attempts = []
    for _ in range(retries + 1):
        reply = call(msgs, response_schema=schema)
        text = reply["text"]
        try:
            obj = parse_json(text)
            errors = validate(obj, schema)
        except ValueError as e:
            obj, errors = None, [str(e)]
        attempt = {"text": text, "errors": errors}
        if reply.get("schema_fallback"):
            attempt["schema_fallback"] = True
        attempts.append(attempt)
        if not errors:
            return obj, attempts
        msgs = msgs + [
            {"role": "assistant", "content": text, "tool_calls": []},
            {"role": "user", "content": "That reply did not match the schema: "
                                        + "; ".join(errors)
                                        + ". Reply again with only a JSON object that matches the schema."},
        ]
    raise SchemaError(attempts)


def finish_json(messages, text, schema, complete=None):
    """The loop's final answer as an object matching schema.

    When the answer text already parses and validates, no model call is
    made. Otherwise the conversation continues with a correction turn and
    complete_json() asks again, up to three times. Returns (object, attempts)
    like complete_json; attempts, and those of a SchemaError, start with the
    answer text itself.
    """
    try:
        obj = parse_json(text or "")
        errors = validate(obj, schema)
    except ValueError as e:
        obj, errors = None, [str(e)]
    attempts = [{"text": text, "errors": errors}]
    if not errors:
        return obj, attempts
    msgs = list(messages) + [
        {"role": "user", "content": "Your answer did not match the required schema: " + "; ".join(errors)
                                    + ". Reply with only a JSON object that matches the schema."}]
    try:
        obj, more = complete_json(msgs, schema, complete)
    except SchemaError as e:
        raise SchemaError(attempts + e.attempts) from None
    return obj, attempts + more
