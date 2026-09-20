"""Static model catalog for the claude-cli provider.

The `claude` CLI exposes no `/models`-equivalent listing endpoint, so this static
list is the only catalog Hermes has for this provider (`supports_model_listing`
is False on the registered profile — see __init__.py). It needs manual maintenance
as Anthropic ships new model generations; see ../../docs/07-scope-and-migration.md.
"""

from __future__ import annotations

FALLBACK_MODELS: tuple[str, ...] = (
    "sonnet",
    "opus",
    "haiku",
    "claude-sonnet-4-6",
    "claude-opus-4-7",
    "claude-haiku-4-5",
)

DEFAULT_AUX_MODEL = "haiku"
