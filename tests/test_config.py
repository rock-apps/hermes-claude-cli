"""Tests for plugin.claude_cli.config."""

from __future__ import annotations

from plugin.claude_cli.config import (
    ClaudeBinaryNotFoundError,
    find_claude_binary,
    load_config,
)


def test_find_claude_binary_prefers_new_env_var_over_legacy() -> None:
    # Arrange
    env = {"CLAUDE_CLI_BIN": "/opt/new/claude", "CLAUDE_BIN": "/opt/legacy/claude"}

    # Act
    result = find_claude_binary(env)

    # Assert
    assert result == "/opt/new/claude"


def test_find_claude_binary_falls_back_to_legacy_env_var() -> None:
    # Arrange
    env = {"CLAUDE_BIN": "/opt/legacy/claude"}

    # Act
    result = find_claude_binary(env)

    # Assert
    assert result == "/opt/legacy/claude"


def test_find_claude_binary_falls_back_to_path_lookup(monkeypatch) -> None:
    # Arrange
    monkeypatch.setattr("plugin.claude_cli.config.os.path.isfile", lambda path: False)
    monkeypatch.setattr(
        "plugin.claude_cli.config.shutil.which", lambda name: "/usr/bin/claude"
    )

    # Act
    result = find_claude_binary({})

    # Assert
    assert result == "/usr/bin/claude"


def test_find_claude_binary_raises_when_nothing_found(monkeypatch) -> None:
    # Arrange
    monkeypatch.setattr("plugin.claude_cli.config.shutil.which", lambda name: None)
    monkeypatch.setattr("plugin.claude_cli.config.os.path.isfile", lambda path: False)

    # Act / Assert
    try:
        find_claude_binary({})
        assert False, "expected ClaudeBinaryNotFoundError"
    except ClaudeBinaryNotFoundError:
        pass


def test_load_config_uses_documented_defaults(monkeypatch) -> None:
    # Arrange
    monkeypatch.setattr(
        "plugin.claude_cli.config.find_claude_binary", lambda env: "/usr/bin/claude"
    )

    # Act
    config = load_config({})

    # Assert
    assert config.binary == "/usr/bin/claude"
    assert config.default_model == "sonnet"
    assert config.allowed_dirs == ()
    assert config.permission_mode == "auto"
    assert config.restricted is True
    assert config.max_budget_usd is None
    assert config.timeout_seconds == 300.0


def test_load_config_allows_disabling_restricted_mode(monkeypatch) -> None:
    # Arrange
    monkeypatch.setattr(
        "plugin.claude_cli.config.find_claude_binary", lambda env: "/usr/bin/claude"
    )

    # Act
    config = load_config({"CLAUDE_CLI_RESTRICTED": "false"})

    # Assert
    assert config.restricted is False


def test_load_config_reads_every_env_var(monkeypatch, tmp_path) -> None:
    # Arrange
    allowed_dir = tmp_path / "workspace"
    allowed_dir.mkdir()
    monkeypatch.setattr(
        "plugin.claude_cli.config.find_claude_binary", lambda env: "/usr/bin/claude"
    )
    env = {
        "CLAUDE_CLI_DEFAULT_MODEL": "opus",
        "CLAUDE_CLI_ALLOWED_DIRS": str(allowed_dir),
        "CLAUDE_CLI_PERMISSION_MODE": "manual",
        "CLAUDE_CLI_RESTRICTED": "true",
        "CLAUDE_CLI_MAX_BUDGET_USD": "2.5",
        "CLAUDE_CLI_TIMEOUT_SECONDS": "60",
    }

    # Act
    config = load_config(env)

    # Assert
    assert config.default_model == "opus"
    assert config.allowed_dirs == (str(allowed_dir),)
    assert config.permission_mode == "manual"
    assert config.restricted is True
    assert config.max_budget_usd == 2.5
    assert config.timeout_seconds == 60.0


def test_load_config_drops_nonexistent_allowed_dirs(monkeypatch, tmp_path) -> None:
    # Arrange
    monkeypatch.setattr(
        "plugin.claude_cli.config.find_claude_binary", lambda env: "/usr/bin/claude"
    )
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    missing_dir = tmp_path / "does-not-exist"
    env = {"CLAUDE_CLI_ALLOWED_DIRS": f"{real_dir}:{missing_dir}"}

    # Act
    config = load_config(env)

    # Assert
    assert config.allowed_dirs == (str(real_dir),)


def test_load_config_expands_home_prefixed_allowed_dirs(monkeypatch) -> None:
    # Arrange
    import os

    monkeypatch.setattr(
        "plugin.claude_cli.config.find_claude_binary", lambda env: "/usr/bin/claude"
    )
    home = os.path.expanduser("~")
    env = {"CLAUDE_CLI_ALLOWED_DIRS": "~"}

    # Act
    config = load_config(env)

    # Assert
    assert config.allowed_dirs == (home,)
