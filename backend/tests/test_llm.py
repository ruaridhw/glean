from __future__ import annotations

from unittest.mock import patch

import pytest

from glean.llm import create_chat_model


class TestCreateChatModel:
    def test_anthropic_returns_chat_anthropic(self) -> None:
        with patch("glean.llm.ChatAnthropic") as mock_cls:
            model = create_chat_model("anthropic", "claude-sonnet-4-6", api_key="test-key")
            mock_cls.assert_called_once_with(model="claude-sonnet-4-6", api_key="test-key")
            assert model is mock_cls.return_value

    def test_google_returns_chat_google(self) -> None:
        with patch("glean.llm.ChatGoogleGenerativeAI") as mock_cls:
            model = create_chat_model("google", "gemma-3", api_key="test-key")
            mock_cls.assert_called_once_with(model="gemma-3", api_key="test-key")
            assert model is mock_cls.return_value

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown LLM provider: foobar"):
            create_chat_model("foobar", "some-model", api_key="test-key")
