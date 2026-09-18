"""ClaudeCLIClient — a `.chat.completions.create(...)`-compatible facade over the
`claude` CLI subprocess.

Mirrors the minimal surface of Hermes Agent's own reference subprocess-backed
provider client (agent/copilot_acp_client.py, used by the bundled `copilot-acp`
provider) — see ../../docs/03-hermes-provider-model.md. No HTTP is involved
anywhere in this module: every call spawns and waits on a `claude` subprocess.

Streaming (`stream=True`) is not implemented as real token-by-token delivery in this
phase — see ../../docs/10-roadmap.md, Fase 2. Passing `tools`/`tool_choice` is
accepted for interface compatibility but has no effect: the `claude` CLI does not
accept externally-defined tool schemas (see ../../docs/06-claude-cli-reference.md);
it always uses its own built-in tools transparently.
"""

from __future__ import annotations

import threading
import time
import uuid
from types import SimpleNamespace
from typing import Any

from .config import ClaudeCLIConfig, load_config
from .process import (
    ClaudeCLIProcessError,
    CLIResult,
    PermissionConfig,
    build_args,
    build_subprocess_env,
    run_once,
)
from .protocol import (
    EmptyMessagesError,
    flatten_messages,
    map_stop_reason,
    normalize_model_alias,
)
from .session import compute_delta


def _effective_timeout(timeout: Any, default: float) -> float:
    """Normalise a float or an httpx.Timeout-like object to wall-clock seconds.

    Hermes' relay layer calls every provider client the same way it would call the
    real OpenAI SDK, which accepts an `httpx.Timeout` object (with `read`/`write`/
    `connect`/`pool` attributes, no single scalar) as well as a bare float — passing
    that object straight into `subprocess.run(timeout=...)` fails with a TypeError
    (verified against a real Hermes Agent process, not assumed). The largest
    component wins, matching the intent of "don't time out before the slowest phase
    would complete".
    """
    if isinstance(timeout, (int, float)):
        return float(timeout)
    if timeout is None:
        return default
    candidates = [getattr(timeout, attr, None) for attr in ("read", "write", "connect", "pool", "timeout")]
    numeric = [float(v) for v in candidates if isinstance(v, (int, float))]
    return max(numeric) if numeric else default


def _permissions_for(config: ClaudeCLIConfig) -> PermissionConfig:
    return PermissionConfig(
        bypass=False,
        mode=config.permission_mode,
        prompts_none=True,
        restricted=config.restricted,
        allowed_dirs=config.allowed_dirs,
    )


def _build_completion(model: str, result: CLIResult) -> SimpleNamespace:
    """Build an OpenAI-chat-completion-shaped object from a parsed CLIResult."""
    finish_reason = "stop" if result.is_error else map_stop_reason(result.stop_reason)
    message = SimpleNamespace(
        role="assistant",
        content=result.text,
        tool_calls=None,
        reasoning=None,
        reasoning_content=None,
    )
    choice = SimpleNamespace(index=0, message=message, finish_reason=finish_reason)
    usage = SimpleNamespace(
        prompt_tokens=result.input_tokens,
        completion_tokens=result.output_tokens,
        total_tokens=result.input_tokens + result.output_tokens,
        prompt_tokens_details=SimpleNamespace(cached_tokens=0),
    )
    completion_id = f"chatcmpl-{result.session_id or uuid.uuid4()}"
    return SimpleNamespace(
        id=completion_id,
        object="chat.completion",
        created=int(time.time()),
        model=model,
        choices=[choice],
        usage=usage,
        is_error=result.is_error,
        error_message=result.error_message,
    )


class ClaudeCLIClient:
    """Minimal OpenAI-client-compatible facade for the `claude` CLI.

    Declared for Hermes' client-construction path: this shim already produces a
    complete, OpenAI-shaped response on its own and is not an HTTP client, so it must
    not be re-wrapped by the generic transport layer.
    """

    HERMES_SKIP_TRANSPORT_WRAP = True

    def __init__(self, *, config: ClaudeCLIConfig | None = None, **_: Any) -> None:
        self._config = config or load_config()
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create_chat_completion)
        )
        # Session-continuity tracking (Fase 4, docs/10-roadmap.md). Scoped to this
        # instance deliberately: Hermes reuses one ClaudeCLIClient across the turns
        # of a conversation (as long as its construction kwargs don't change), so
        # instance state is a safe place for this. A lock guards it because Hermes
        # *can* hand out a fresh instance for a genuinely concurrent call on the
        # same conversation (its own per-request client slot has an `in_use` guard
        # that does exactly this) — but if some caller ever does share one instance
        # across concurrent turns, this keeps the read-decide-write sequence atomic
        # instead of racing two turns onto the same tracked session id.
        self._session_lock = threading.Lock()
        self._last_messages: list[dict[str, Any]] | None = None
        self._last_session_id: str | None = None
        self._last_model: str | None = None

    def close(self) -> None:
        """No-op: each call is a self-contained subprocess with nothing kept open
        between requests. Present only because Hermes' cleanup path calls `close()`
        unconditionally on every provider client (verified against a real Hermes
        Agent process — without this, cleanup logs a harmless but noisy
        AttributeError at debug level)."""

    def _run_turn(
        self, *, resolved_model: str, messages: list[dict[str, Any]], timeout: float
    ) -> CLIResult:
        config = self._config
        resume_id: str | None = None
        delta_prompt: str | None = None

        if config.session_continuity:
            with self._session_lock:
                if resolved_model == self._last_model:
                    delta = compute_delta(self._last_messages, messages)
                    if delta is not None:
                        try:
                            _, delta_prompt = flatten_messages(delta)
                        except EmptyMessagesError:
                            delta_prompt = None
                        if delta_prompt:
                            resume_id = self._last_session_id

        result: CLIResult | None = None
        if resume_id and delta_prompt:
            resume_args = build_args(
                model=resolved_model,
                system_prompt="",
                prompt=delta_prompt,
                permissions=_permissions_for(config),
                max_budget_usd=config.max_budget_usd,
                resume_session_id=resume_id,
            )
            try:
                result = run_once(
                    config.binary, resume_args, env=build_subprocess_env(), timeout=timeout
                )
            except ClaudeCLIProcessError:
                # The session claude knows about is gone (expired, compacted, or
                # otherwise unresumable) — verified empirically that an unknown
                # --resume target fails with empty/unparseable stdout and a plain
                # stderr message, not a normal is_error=true JSON result, so
                # run_once raises rather than returning a CLIResult here. Drop the
                # stale tracking and fall through to a full, fresh call below.
                with self._session_lock:
                    self._last_session_id = None
                    self._last_messages = None

        if result is None:
            system_prompt, prompt = flatten_messages(messages)
            fresh_args = build_args(
                model=resolved_model,
                system_prompt=system_prompt,
                prompt=prompt,
                permissions=_permissions_for(config),
                max_budget_usd=config.max_budget_usd,
            )
            result = run_once(
                config.binary, fresh_args, env=build_subprocess_env(), timeout=timeout
            )

        if config.session_continuity:
            with self._session_lock:
                if result.is_error:
                    self._last_session_id = None
                    self._last_messages = None
                else:
                    self._last_session_id = result.session_id or None
                    self._last_messages = list(messages)
                    self._last_model = resolved_model

        return result

    def _create_chat_completion(
        self,
        *,
        model: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = None,
        timeout: float | None = None,
        **_: Any,
    ) -> Any:
        config = self._config
        resolved_model = normalize_model_alias(model or "", config.default_model)
        result = self._run_turn(
            resolved_model=resolved_model,
            messages=messages or [],
            timeout=_effective_timeout(timeout, config.timeout_seconds),
        )
        completion = _build_completion(resolved_model, result)
        if not stream:
            return completion
        # Real per-token delivery is Fase 2 (see ../../docs/10-roadmap.md); for now,
        # mirror Hermes' own copilot-acp reference client and re-shape the one-shot
        # completion into OpenAI stream chunks via Hermes' shared helper — a stream
        # consumer expects `.choices[i].delta`, not `.choices[i].message` (verified
        # against a real Hermes Agent process: yielding the completion object
        # directly raised "'SimpleNamespace' object has no attribute 'delta'").
        # Only importable inside a real Hermes process, same as the `providers`
        # import in __init__.py.
        from agent.acp_openai_bridge import completion_to_stream_chunks

        return completion_to_stream_chunks(completion)
