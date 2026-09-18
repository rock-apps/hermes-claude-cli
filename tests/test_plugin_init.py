"""Tests for plugin.claude_cli's package-level provider registration.

Outside a real Hermes Agent process, `providers`/`providers.base` are not
importable — the package must degrade to a no-op import in that case, not raise.
"""

from __future__ import annotations

import importlib


def test_package_imports_cleanly_without_hermes_providers_package() -> None:
    # Arrange / Act
    module = importlib.import_module("plugin.claude_cli")

    # Assert
    assert module.ProviderProfile is None
    assert module.register_provider is None
    assert not hasattr(module, "claude_cli")
