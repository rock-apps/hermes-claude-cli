"""ClaudeCLIClient — a `.chat.completions.create(...)`-compatible facade over the
`claude` CLI subprocess.

Mirrors the minimal surface of Hermes Agent's own reference subprocess-backed
provider client (agent/copilot_acp_client.py, used by the bundled `copilot-acp`
provider) — see ../../docs/03-modelo-de-provider-do-hermes.md. No HTTP is involved
anywhere in this module: every call spawns and waits on a `claude` subprocess.

Streaming (`stream=True`) is not implemented as real token-by-token delivery in this
phase — see ../../docs/10-roadmap.md, Fase 2. Passing `tools`/`tool_choice` is
accepted for interface compatibility but has no effect: the `claude` CLI does not
accept externally-defined tool schemas (see ../../docs/06-referencia-cli-claude.md);
it always uses its own built-in tools transparently.
"""

from __future__ import annotations

import time
import uuid
from types import SimpleNamespace
from typing import Any

from .config import ClaudeCLIConfig, load_config
from .process import (
    CLIResult,
    PermissionConfig,
    build_args,
    build_subprocess_env,
    run_once,
)
from .protocol import flatten_messages, map_stop_reason, normalize_model_alias


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

    def close(self) -> None:
        """No-op: each call is a self-contained subprocess with nothing kept open
        between requests. Present only because Hermes' cleanup path calls `close()`
        unconditionally on every provider client (verified against a real Hermes
        Agent process — without this, cleanup logs a harmless but noisy
        AttributeError at debug level)."""

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
        system_prompt, prompt = flatten_messages(messages or [])
        args = build_args(
            model=resolved_model,
            system_prompt=system_prompt,
            prompt=prompt,
            permissions=_permissions_for(config),
            max_budget_usd=config.max_budget_usd,
        )
        result = run_once(
            config.binary,
            args,
            env=build_subprocess_env(),
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
