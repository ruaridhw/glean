from __future__ import annotations

from unittest.mock import patch

from glean.llm import create_chat_model


class TestCreateChatModel:
    def test_returns_chat_open_router(self) -> None:
        with patch("glean.llm.ChatOpenRouter") as mock_cls:
            model = create_chat_model("anthropic/claude-sonnet-4.6", api_key="test-key")
            mock_cls.assert_called_once_with(
                model="anthropic/claude-sonnet-4.6", openrouter_api_key="test-key"
            )
            assert model is mock_cls.return_value
