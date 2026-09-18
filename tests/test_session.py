"""Tests for plugin.claude_cli.session (pure delta-detection logic)."""

from __future__ import annotations

from plugin.claude_cli.session import compute_delta


def test_no_previous_messages_returns_none() -> None:
    # Arrange
    current = [{"role": "user", "content": "hi"}]

    # Act
    delta = compute_delta(None, current)

    # Assert
    assert delta is None


def test_empty_previous_messages_returns_none() -> None:
    # Arrange
    current = [{"role": "user", "content": "hi"}]

    # Act
    delta = compute_delta([], current)

    # Assert
    assert delta is None


def test_current_not_longer_than_previous_returns_none() -> None:
    # Arrange
    previous = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    current = [{"role": "user", "content": "hi"}]

    # Act
    delta = compute_delta(previous, current)

    # Assert
    assert delta is None


def test_extension_returns_the_new_messages_only() -> None:
    # Arrange
    previous = [{"role": "user", "content": "my favorite number is 9"}]
    current = previous + [
        {"role": "assistant", "content": "Got it, 9."},
        {"role": "user", "content": "what is it plus 1?"},
    ]

    # Act
    delta = compute_delta(previous, current)

    # Assert
    assert delta == [
        {"role": "assistant", "content": "Got it, 9."},
        {"role": "user", "content": "what is it plus 1?"},
    ]


def test_rewritten_history_returns_none_even_if_longer() -> None:
    # Arrange: same length prefix would match, but content differs — e.g. Hermes'
    # context compression rewrote the transcript.
    previous = [{"role": "user", "content": "original message"}]
    current = [
        {"role": "user", "content": "compressed summary instead"},
        {"role": "user", "content": "new message"},
    ]

    # Act
    delta = compute_delta(previous, current)

    # Assert
    assert delta is None


def test_identical_length_and_content_with_no_new_messages_returns_none() -> None:
    # Arrange
    previous = [{"role": "user", "content": "hi"}]
    current = [{"role": "user", "content": "hi"}]

    # Act
    delta = compute_delta(previous, current)

    # Assert
    assert delta is None
