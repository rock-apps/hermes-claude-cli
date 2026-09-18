"""Pure logic for deciding whether a chat turn can resume a prior `claude` CLI
session instead of re-sending the full flattened conversation history.

No subprocess/I/O here — see client.py for how this plugs into an actual call, and
../../docs/10-roadmap.md (Fase 4) for the empirical findings that justify this
design: a `ClaudeCLIClient` instance is reused by Hermes across the turns of one
conversation (as long as its construction kwargs don't change), so per-instance
state is a safe place to track "what did I last send, and under what claude
session_id" — with a natural, safe fallback whenever that assumption doesn't hold
(a fresh instance simply starts with no tracked state, so it makes a normal,
full-history call).
"""

from __future__ import annotations

from typing import Any


def compute_delta(
    previous_messages: list[dict[str, Any]] | None,
    current_messages: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    """Return the messages appended since `previous_messages`, or None when
    continuity can't be trusted for this call.

    None (meaning: don't try to resume, send `current_messages` fresh instead) when
    any of these hold:
      - `previous_messages` is None or empty (nothing to compare against yet).
      - `current_messages` is not longer than `previous_messages`.
      - `current_messages`'s first `len(previous_messages)` entries don't match
        `previous_messages` exactly (the history was rewritten — e.g. Hermes'
        context compression ran, or this is an unrelated conversation reusing the
        same client instance) — trusting a resume here could send `claude` a
        follow-up that silently contradicts what it still has from the old,
        no-longer-current history.
      - the computed delta is empty (defensive; the "not longer than" check above
        already covers the normal case).
    """
    if not previous_messages:
        return None
    if len(current_messages) <= len(previous_messages):
        return None
    if current_messages[: len(previous_messages)] != previous_messages:
        return None
    delta = current_messages[len(previous_messages) :]
    return delta or None
