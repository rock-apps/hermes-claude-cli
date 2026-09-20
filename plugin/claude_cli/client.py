"""ClaudeCLIClient — a `.chat.completions.create(...)`-compatible facade over the
`claude` CLI subprocess.

Mirrors the minimal surface of Hermes Agent's own reference subprocess-backed
provider client (agent/copilot_acp_client.py, used by the bundled `copilot-acp`
provider) — see ../../docs/03-hermes-provider-model.md. No HTTP is involved
anywhere in this module: every call spawns and waits on a `claude` subprocess.

Streaming (`stream=True`) delivers real incremental text/reasoning as `claude`
produces it (`--output-format stream-json --include-partial-messages`), verified
against a real invocation — see `process.run_streaming`. Passing `tools`/
`tool_choice` is accepted for interface compatibility but has no effect: the
`claude` CLI does not accept externally-defined tool schemas (see
../../docs/06-claude-cli-reference.md); it always uses its own built-in tools
transparently.
"""

from __future__ import annotations

import json
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
    StreamChunk,
    build_args,
    build_subprocess_env,
    run_once,
    run_streaming,
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
    extra_settings = (
        json.dumps({"permissions": {"allow": list(config.allowed_tools)}})
        if config.allowed_tools
        else None
    )
    return PermissionConfig(
        bypass=False,
        mode=config.permission_mode,
        prompts_none=True,
        restricted=config.restricted,
        allowed_dirs=config.allowed_dirs,
        mcp_config=config.mcp_config,
        extra_settings=extra_settings,
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

    def _decide_call(
        self, resolved_model: str, messages: list[dict[str, Any]]
    ) -> tuple[str, str, str | None]:
        """Decide the (system_prompt, prompt, resume_session_id) for one call
        attempt. `resume_session_id` is None when continuity is off, this is the
        first turn tracked, the model changed, or the history isn't a trusted
        extension of what was last sent (see `session.compute_delta`) — in every
        one of those cases the caller gets the full flattened history instead."""
        config = self._config
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
                            return "", delta_prompt, self._last_session_id
        system_prompt, prompt = flatten_messages(messages)
        return system_prompt, prompt, None

    def _record_result(
        self, resolved_model: str, messages: list[dict[str, Any]], result: CLIResult
    ) -> None:
        if not self._config.session_continuity:
            return
        with self._session_lock:
            if result.is_error:
                self._last_session_id = None
                self._last_messages = None
            else:
                self._last_session_id = result.session_id or None
                self._last_messages = list(messages)
                self._last_model = resolved_model

    def _run_turn(
        self, *, resolved_model: str, messages: list[dict[str, Any]], timeout: float
    ) -> CLIResult:
        config = self._config
        system_prompt, prompt, resume_id = self._decide_call(resolved_model, messages)

        result: CLIResult | None = None
        if resume_id:
            resume_args = build_args(
                model=resolved_model,
                system_prompt=system_prompt,
                prompt=prompt,
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
                # otherwise unresumable) — verified empirically that in
                # --output-format json mode an unknown --resume target fails with
                # empty/unparseable stdout and a plain stderr message, not a normal
                # is_error=true JSON result, so run_once raises rather than
                # returning a CLIResult here. Drop the stale tracking and fall
                # through to a full, fresh call below.
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

        self._record_result(resolved_model, messages, result)
        return result

    def _run_turn_streaming(
        self, *, resolved_model: str, messages: list[dict[str, Any]], timeout: float
    ):
        config = self._config
        env = build_subprocess_env()
        system_prompt, prompt, resume_id = self._decide_call(resolved_model, messages)

        def stream_once(sp: str, p: str, rid: str | None):
            args = build_args(
                model=resolved_model,
                system_prompt=sp,
                prompt=p,
                permissions=_permissions_for(config),
                max_budget_usd=config.max_budget_usd,
                resume_session_id=rid,
                stream=True,
            )
            return run_streaming(config.binary, args, env=env, timeout=timeout)

        yielded_content = False
        final_result: CLIResult | None = None
        try:
            for chunk in stream_once(system_prompt, prompt, resume_id):
                if chunk.is_final:
                    final_result = chunk.result
                    break
                if chunk.text_delta or chunk.reasoning_delta:
                    yielded_content = True
                yield chunk
        except ClaudeCLIProcessError:
            # Mirrors _run_turn's resume-failure handling — verified empirically
            # this specific exception path (nothing parseable at all) is rarer in
            # streaming mode than in run_once, but stays possible (e.g. the
            # process crashes before any event, or the timeout fires). Only safe
            # to retry silently if nothing was yielded to the caller yet.
            if resume_id and not yielded_content:
                with self._session_lock:
                    self._last_session_id = None
                    self._last_messages = None
                system_prompt, prompt = flatten_messages(messages)
                for chunk in stream_once(system_prompt, prompt, None):
                    if chunk.is_final:
                        self._record_result(resolved_model, messages, chunk.result)
                    yield chunk
                return
            raise

        if resume_id and final_result is not None and final_result.is_error and not yielded_content:
            # Verified empirically: unlike run_once, an unknown --resume target in
            # streaming mode does NOT raise — it comes back as a normal terminal
            # chunk with is_error=True and empty text. Safe to retry fresh since
            # nothing was yielded to the caller yet.
            with self._session_lock:
                self._last_session_id = None
                self._last_messages = None
            system_prompt, prompt = flatten_messages(messages)
            for chunk in stream_once(system_prompt, prompt, None):
                if chunk.is_final:
                    self._record_result(resolved_model, messages, chunk.result)
                yield chunk
            return

        if final_result is not None:
            self._record_result(resolved_model, messages, final_result)
            yield StreamChunk(is_final=True, result=final_result)

    def _stream_openai_chunks(self, resolved_model: str, chunks: Any) -> Any:
        """Convert `StreamChunk`s into the OpenAI `chat.completion.chunk` shape a
        stream consumer expects: `.choices[i].delta.content` /
        `.delta.reasoning_content`, not `.choices[i].message` — verified against a
        real Hermes Agent process (yielding a full completion object for a
        streaming call raised "'SimpleNamespace' object has no attribute
        'delta'")."""
        completion_id = f"chatcmpl-{uuid.uuid4()}"
        created = int(time.time())
        for chunk in chunks:
            if chunk.is_final:
                result = chunk.result
                finish_reason = "stop" if result.is_error else map_stop_reason(result.stop_reason)
                delta_kwargs: dict[str, Any] = {}
                if result.is_error and result.text:
                    delta_kwargs["content"] = result.text
                yield SimpleNamespace(
                    id=completion_id,
                    object="chat.completion.chunk",
                    created=created,
                    model=resolved_model,
                    choices=[
                        SimpleNamespace(
                            index=0,
                            delta=SimpleNamespace(**delta_kwargs),
                            finish_reason=finish_reason,
                        )
                    ],
                    usage=SimpleNamespace(
                        prompt_tokens=result.input_tokens,
                        completion_tokens=result.output_tokens,
                        total_tokens=result.input_tokens + result.output_tokens,
                        prompt_tokens_details=SimpleNamespace(cached_tokens=0),
                    ),
                )
                return
            delta_kwargs = {}
            if chunk.text_delta:
                delta_kwargs["content"] = chunk.text_delta
            if chunk.reasoning_delta:
                delta_kwargs["reasoning_content"] = chunk.reasoning_delta
            if not delta_kwargs:
                continue
            yield SimpleNamespace(
                id=completion_id,
                object="chat.completion.chunk",
                created=created,
                model=resolved_model,
                choices=[
                    SimpleNamespace(index=0, delta=SimpleNamespace(**delta_kwargs), finish_reason=None)
                ],
                usage=None,
            )

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
        effective_timeout = _effective_timeout(timeout, config.timeout_seconds)

        if stream:
            chunks = self._run_turn_streaming(
                resolved_model=resolved_model, messages=messages or [], timeout=effective_timeout
            )
            return self._stream_openai_chunks(resolved_model, chunks)

        result = self._run_turn(
            resolved_model=resolved_model, messages=messages or [], timeout=effective_timeout
        )
        return _build_completion(resolved_model, result)
