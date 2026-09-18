"""Tests for plugin.claude_cli.protocol."""

from __future__ import annotations

import pytest

from plugin.claude_cli.protocol import (
    EmptyMessagesError,
    flatten_messages,
    map_stop_reason,
    normalize_model_alias,
    stringify_content,
)

# --- stringify_content ---------------------------------------------------


def test_stringify_content_plain_string_passthrough():
    # Arrange
    content = "hello world"

    # Act
    result = stringify_content(content)

    # Assert
    assert result == "hello world"


def test_stringify_content_list_with_single_text_part():
    # Arrange
    content = [{"type": "text", "text": "hello"}]

    # Act
    result = stringify_content(content)

    # Assert
    assert result == "hello"


def test_stringify_content_list_with_multiple_text_parts_concatenated():
    # Arrange
    content = [{"type": "text", "text": "hello "}, {"type": "text", "text": "world"}]

    # Act
    result = stringify_content(content)

    # Assert
    assert result == "hello world"


def test_stringify_content_list_ignores_non_text_parts():
    # Arrange
    content = [
        {"type": "image_url", "image_url": {"url": "data:..."}},
        {"type": "text", "text": "only this"},
    ]

    # Act
    result = stringify_content(content)

    # Assert
    assert result == "only this"


def test_stringify_content_none_returns_empty_string():
    # Arrange
    content = None

    # Act
    result = stringify_content(content)

    # Assert
    assert result == ""


def test_stringify_content_unsupported_types_return_empty_string():
    # Arrange / Act / Assert
    assert stringify_content(42) == ""
    assert stringify_content({"no": "type key"}) == ""


# --- flatten_messages -----------------------------------------------------


def test_flatten_messages_empty_list_raises():
    # Arrange
    messages: list[dict] = []

    # Act / Assert
    with pytest.raises(EmptyMessagesError):
        flatten_messages(messages)


def test_flatten_messages_single_user_message_has_no_wrapper():
    # Arrange
    messages = [{"role": "user", "content": "hi there"}]

    # Act
    system_prompt, prompt = flatten_messages(messages)

    # Assert
    assert system_prompt == ""
    assert prompt == "hi there"


def test_flatten_messages_system_and_user():
    # Arrange
    messages = [
        {"role": "system", "content": "be nice"},
        {"role": "user", "content": "hi there"},
    ]

    # Act
    system_prompt, prompt = flatten_messages(messages)

    # Assert
    assert system_prompt == "be nice"
    assert prompt == "hi there"


def test_flatten_messages_multiple_system_messages_joined_in_order():
    # Arrange
    messages = [
        {"role": "system", "content": "first"},
        {"role": "system", "content": "second"},
        {"role": "user", "content": "hi"},
    ]

    # Act
    system_prompt, _ = flatten_messages(messages)

    # Assert
    assert system_prompt == "first\n\nsecond"


def test_flatten_messages_multi_turn_conversation_wraps_prior_context():
    # Arrange
    messages = [
        {"role": "system", "content": "be nice"},
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
        {"role": "user", "content": "second question"},
    ]

    # Act
    system_prompt, prompt = flatten_messages(messages)

    # Assert
    assert system_prompt == "be nice"
    assert prompt.startswith("Prior conversation:\n")
    assert "USER:\nfirst question" in prompt
    assert "ASSISTANT:\nfirst answer" in prompt
    assert prompt.endswith("Current message:\nsecond question")
    # The last user message must not appear a second time inline in the transcript.
    assert prompt.count("second question") == 1


def test_flatten_messages_skips_blocks_with_empty_stringified_content():
    # Arrange
    messages = [
        {"role": "assistant", "content": None},
        {"role": "user", "content": "hi"},
    ]

    # Act
    _, prompt = flatten_messages(messages)

    # Assert
    assert "ASSISTANT" not in prompt
    assert prompt == "hi"


def test_flatten_messages_no_user_message_yields_empty_current_message():
    # Arrange
    messages = [{"role": "system", "content": "be nice"}]

    # Act
    system_prompt, prompt = flatten_messages(messages)

    # Assert
    assert system_prompt == "be nice"
    assert prompt == ""


# --- normalize_model_alias -------------------------------------------------


def test_normalize_model_alias_empty_model_falls_back_and_still_collapses():
    # Arrange
    model = ""
    default_model = "claude-sonnet-4-6"

    # Act
    result = normalize_model_alias(model, default_model)

    # Assert
    assert result == "sonnet"


def test_normalize_model_alias_versioned_id_collapses_to_alias():
    # Arrange / Act
    result = normalize_model_alias("claude-opus-4-7", "sonnet")

    # Assert
    assert result == "opus"


def test_normalize_model_alias_is_case_insensitive():
    # Arrange / Act
    result = normalize_model_alias("HAIKU-preview", "sonnet")

    # Assert
    assert result == "haiku"


def test_normalize_model_alias_unrelated_string_returned_unchanged():
    # Arrange / Act
    result = normalize_model_alias("gpt-4o", "sonnet")

    # Assert
    assert result == "gpt-4o"


def test_normalize_model_alias_sonnet_checked_before_opus_and_haiku():
    # Arrange / Act / Assert
    assert normalize_model_alias("claude-sonnet-4-6", "sonnet") == "sonnet"
    assert normalize_model_alias("claude-opus-4-7", "sonnet") == "opus"
    assert normalize_model_alias("claude-haiku-4-5", "sonnet") == "haiku"


# --- map_stop_reason ---------------------------------------------------


def test_map_stop_reason_end_turn():
    assert map_stop_reason("end_turn") == "stop"


def test_map_stop_reason_max_tokens():
    assert map_stop_reason("max_tokens") == "length"


def test_map_stop_reason_tool_use():
    assert map_stop_reason("tool_use") == "tool_calls"


def test_map_stop_reason_none_defaults_to_stop():
    assert map_stop_reason(None) == "stop"


def test_map_stop_reason_unrecognized_defaults_to_stop():
    assert map_stop_reason("something_else") == "stop"
