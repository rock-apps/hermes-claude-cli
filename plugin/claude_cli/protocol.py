"""Translation between OpenAI-style chat messages and the `claude` CLI's prompt/flag interface.

Pure message <-> prompt translation, no I/O — cost/usage parsing from the CLI's
actual JSON output lives in process.py, not here.
"""

from __future__ import annotations


class EmptyMessagesError(ValueError):
    """Raised when flatten_messages is called with an empty message list."""


def stringify_content(content: object) -> str:
    """Extract plain text from an OpenAI-style message `content` field.

    A plain string is returned as-is. A list of content parts concatenates only the
    parts that are a dict with `"type": "text"` and a string `"text"` field, in
    order, with no separator — other part types (e.g. images) are ignored, since
    vision is not supported over this path: the `claude` CLI only accepts a plain
    text prompt. Anything else returns "".
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if (
                isinstance(part, dict)
                and part.get("type") == "text"
                and isinstance(part.get("text"), str)
            ):
                parts.append(part["text"])
        return "".join(parts)
    return ""


def flatten_messages(messages: list[dict]) -> tuple[str, str]:
    """Flatten an OpenAI-style message list into (system_prompt, prompt).

    Every "system" message contributes its stringified content to `system_prompt`,
    joined by "\\n\\n" (empty ones contribute nothing, no stray separator). The last
    "user" message becomes the "current message"; every other, non-system message
    becomes a "{ROLE_UPPER}:\\n{text}" block in a transcript (messages that
    stringify to "" are skipped). When the transcript is non-empty, `prompt` wraps
    it with "Prior conversation:" / "Current message:" framing around the current
    message; otherwise `prompt` is just the current message (which is "" if there
    was no user message at all).

    Raises EmptyMessagesError if `messages` is empty.
    """
    if not messages:
        raise EmptyMessagesError("flatten_messages requires a non-empty message list")

    last_user_index = -1
    for index, message in enumerate(messages):
        if message.get("role") == "user":
            last_user_index = index

    system_parts: list[str] = []
    transcript_blocks: list[str] = []
    current = ""

    for index, message in enumerate(messages):
        role = message.get("role")
        text = stringify_content(message.get("content"))

        if role == "system":
            if text:
                system_parts.append(text)
            continue

        if index == last_user_index:
            current = text
            continue

        if text:
            transcript_blocks.append(f"{str(role).upper()}:\n{text}")

    system_prompt = "\n\n".join(system_parts)
    transcript = "\n\n".join(transcript_blocks)

    if transcript:
        prompt = f"Prior conversation:\n{transcript}\n\n---\n\nCurrent message:\n{current}"
    else:
        prompt = current

    return system_prompt, prompt


def normalize_model_alias(model: str, default_model: str) -> str:
    """Resolve a Hermes-requested model string to a `claude` CLI model argument.

    Falls back to `default_model` when `model` is falsy, then case-insensitively
    checks the working value for "sonnet", "opus", "haiku" in that order (first
    match wins) and returns the matched bare lowercase alias — this deliberately
    collapses even a fully versioned id like "claude-sonnet-4-6" down to "sonnet",
    since bare aliases always resolve to Anthropic's current latest stable model for
    that tier. If none match, the working value is returned unchanged (original
    casing preserved), on the assumption it's already a full model id the CLI
    understands.
    """
    working = model or default_model
    lowered = working.lower()
    for alias in ("sonnet", "opus", "haiku"):
        if alias in lowered:
            return alias
    return working


_STOP_REASON_MAP = {
    "end_turn": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
}


def map_stop_reason(claude_stop_reason: str | None) -> str:
    """Map a `claude` CLI `stop_reason` value to an OpenAI-style `finish_reason`.

    "end_turn" -> "stop", "max_tokens" -> "length", "tool_use" -> "tool_calls".
    Anything else, including None or an unrecognized string, -> "stop".
    """
    return _STOP_REASON_MAP.get(claude_stop_reason or "", "stop")
