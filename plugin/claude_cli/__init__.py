"""claude-cli provider profile for Hermes Agent.

Registers a `claude-cli` provider that drives the local `claude` CLI (Claude Code)
directly as a subprocess — no HTTP server involved anywhere. Every request runs
against the Claude Code subscription's base plan allowance instead of per-token API
credits.

Architecture rationale and the decision not to use an HTTP bridge are in
../../docs/02-is-bridge-necessary.md and
../../docs/03-unified-architecture.md. The `auth_type="external_process"` +
`create_client()` pattern used below mirrors Hermes Agent's own bundled
`copilot-acp` provider — see ../../docs/01-hermes-provider-model.md.

This module is only meaningful when imported inside a running Hermes Agent process
(it needs the `providers` package on sys.path). Importing it anywhere else — e.g.
this project's own test suite — is a no-op: the `providers` import is guarded, and
if it's unavailable, `claude_cli` below is simply never registered.
"""

from __future__ import annotations

from typing import Any

from .client import ClaudeCLIClient
from .models import DEFAULT_AUX_MODEL, FALLBACK_MODELS

try:
    from providers import register_provider
    from providers.base import ProviderProfile
except ImportError:
    register_provider = None
    ProviderProfile = None


if ProviderProfile is not None:

    class ClaudeCLIProviderProfile(ProviderProfile):
        """Claude CLI — external process, no REST endpoint of its own."""

        def create_client(self, **client_kwargs: Any) -> ClaudeCLIClient:
            return ClaudeCLIClient(**client_kwargs)

    claude_cli = ClaudeCLIProviderProfile(
        name="claude-cli",
        aliases=("claude", "claude-code", "claude-max", "claude-subscription"),
        display_name="Claude CLI (Max subscription)",
        description=(
            "Claude via the local claude CLI subscription — uses Max base "
            "allowance instead of API credits. Runs as a direct subprocess, no "
            "bridge server involved."
        ),
        signup_url="https://claude.ai/code",
        auth_type="external_process",
        base_url="process://claude-cli",
        process_command="claude",
        process_command_env_vars=("CLAUDE_CLI_BIN", "CLAUDE_BIN"),
        fallback_models=FALLBACK_MODELS,
        default_aux_model=DEFAULT_AUX_MODEL,
        supports_model_listing=False,
    )

    register_provider(claude_cli)
