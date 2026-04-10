from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from glean.llm import create_chat_model, validate_model


class TestCreateChatModel:
    def test_returns_chat_open_router(self) -> None:
        with patch("glean.llm.ChatOpenRouter") as mock_cls:
            model = create_chat_model("anthropic/claude-sonnet-4.6", api_key="test-key")
            mock_cls.assert_called_once_with(
                model="anthropic/claude-sonnet-4.6", openrouter_api_key="test-key"
            )
            assert model is mock_cls.return_value


def _mock_models_response(model_ids: list[str]) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"data": [{"id": mid} for mid in model_ids]}
    return resp


class TestValidateModel:
    def test_valid_model_passes(self) -> None:
        resp = _mock_models_response(["anthropic/claude-sonnet-4.6", "google/gemma-4-26b-a4b-it:free"])
        with patch("glean.llm.httpx.get", return_value=resp):
            validate_model("anthropic/claude-sonnet-4.6")  # should not raise

    def test_unknown_model_raises(self) -> None:
        resp = _mock_models_response(["anthropic/claude-sonnet-4.6"])
        with (
            patch("glean.llm.httpx.get", return_value=resp),
            pytest.raises(ValueError, match="Unknown OpenRouter model"),
        ):
            validate_model("nonexistent/model-99")
