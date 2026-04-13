from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from glean.llm import create_chat_model, validate_model


class TestCreateChatModel:
    def test_returns_chat_open_router(self) -> None:
        with patch("glean.llm.ChatOpenRouter") as mock_cls:
            model = create_chat_model("anthropic/claude-sonnet-4.6", api_key="test-key")
            mock_cls.assert_called_once_with(
                model="anthropic/claude-sonnet-4.6", openrouter_api_key="test-key", max_retries=0
            )
            assert model is mock_cls.return_value

    def test_forwards_kwargs(self) -> None:
        with patch("glean.llm.ChatOpenRouter") as mock_cls:
            create_chat_model("anthropic/claude-sonnet-4.6", api_key="test-key", max_tokens=20, temperature=0.5)
            mock_cls.assert_called_once_with(
                model="anthropic/claude-sonnet-4.6",
                openrouter_api_key="test-key",
                max_tokens=20,
                temperature=0.5,
                max_retries=0,
            )

    def test_caller_can_override_max_retries(self) -> None:
        with patch("glean.llm.ChatOpenRouter") as mock_cls:
            create_chat_model("anthropic/claude-sonnet-4.6", api_key="test-key", max_retries=2)
            mock_cls.assert_called_once_with(
                model="anthropic/claude-sonnet-4.6",
                openrouter_api_key="test-key",
                max_retries=2,
            )


def _mock_model_objects(model_ids: list[str]) -> list[MagicMock]:
    return [MagicMock(id=mid) for mid in model_ids]


class TestValidateModel:
    def test_valid_model_passes(self) -> None:
        mock_client = MagicMock()
        mock_client.models.list.return_value.data = _mock_model_objects(
            ["anthropic/claude-sonnet-4.6", "google/gemma-4-26b-a4b-it:free"]
        )
        with patch("glean.llm.OpenRouter", return_value=mock_client):
            validate_model("anthropic/claude-sonnet-4.6", api_key="test-key")

    def test_unknown_model_raises(self) -> None:
        mock_client = MagicMock()
        mock_client.models.list.return_value.data = _mock_model_objects(["anthropic/claude-sonnet-4.6"])
        with (
            patch("glean.llm.OpenRouter", return_value=mock_client),
            pytest.raises(ValueError, match="Unknown OpenRouter model"),
        ):
            validate_model("nonexistent/model-99", api_key="test-key")
