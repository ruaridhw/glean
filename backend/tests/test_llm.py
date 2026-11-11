from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from pydantic import BaseModel, SecretStr, ValidationError

from glean.config import Settings
from glean.llm import (
    DEFAULT_LLM_MODEL_POLICY,
    Feature,
    ImagePart,
    LLMModelPolicy,
    LLMOutputTruncatedError,
    LLMRouter,
    ModelPurpose,
    create_chat_model,
    invoke_structured,
    validate_model,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


class _StructuredTestResponse(BaseModel):
    name: str
    values: list[str]


def _invoke_and_capture(router: LLMRouter, **invoke_kwargs: Any) -> tuple[MagicMock, list[Any]]:
    """Invoke *router* against a patched ChatOpenRouter; return the patched class and the messages the model got."""
    with patch("glean.llm.ChatOpenRouter") as chat_open_router:
        structured = chat_open_router.return_value.with_structured_output.return_value
        structured.invoke.return_value = _StructuredTestResponse(name="Pantry", values=["milk"])
        router.invoke(Feature.RECEIPT_SCAN, _StructuredTestResponse, **invoke_kwargs)
    (messages,), _ = structured.invoke.call_args
    return chat_open_router, messages


def _without_ids(blocks: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """LangChain stamps each content block with a random id; compare everything else."""
    return [{key: value for key, value in block.items() if key != "id"} for block in blocks]


class TestCreateChatModel:
    def test_returns_chat_open_router(self) -> None:
        api_key = SecretStr("test-key")
        with patch("glean.llm.ChatOpenRouter") as mock_cls:
            model = create_chat_model("anthropic/claude-sonnet-4.6", api_key=api_key)
            mock_cls.assert_called_once_with(
                model="anthropic/claude-sonnet-4.6",
                openrouter_api_key=api_key,
                max_retries=0,
                request_timeout=10_000,
            )
            assert model is mock_cls.return_value

    def test_forwards_kwargs(self) -> None:
        api_key = SecretStr("test-key")
        with patch("glean.llm.ChatOpenRouter") as mock_cls:
            create_chat_model("anthropic/claude-sonnet-4.6", api_key=api_key, max_tokens=20, temperature=0.5)
            mock_cls.assert_called_once_with(
                model="anthropic/claude-sonnet-4.6",
                openrouter_api_key=api_key,
                max_tokens=20,
                temperature=0.5,
                max_retries=0,
                request_timeout=10_000,
            )

    def test_caller_can_override_max_retries(self) -> None:
        api_key = SecretStr("test-key")
        with patch("glean.llm.ChatOpenRouter") as mock_cls:
            create_chat_model("anthropic/claude-sonnet-4.6", api_key=api_key, max_retries=2)
            mock_cls.assert_called_once_with(
                model="anthropic/claude-sonnet-4.6",
                openrouter_api_key=api_key,
                max_retries=2,
                request_timeout=10_000,
            )


class TestFeatureMetadata:
    def test_ai_workflow_feature_values_match_langsmith_tags(self) -> None:
        assert Feature.RECEIPT_SCAN == "receipt-scan"
        assert Feature.PANTRY_PURCHASE_DESCRIPTION == "pantry-purchase-description"
        assert Feature.MEAL_PLAN_GENERATION == "meal-plan-generation"
        assert Feature.SHOPPING_LIST_DESCRIPTION == "shopping-list-description"
        assert Feature.RECIPE_IMPORT == "recipe-import"


class TestLLMRouter:
    def test_default_policy_matches_issue_77_model_choices(self) -> None:
        assert DEFAULT_LLM_MODEL_POLICY[Feature.SHOPPING_LIST_DESCRIPTION].production_model == (
            "google/gemini-2.5-flash-lite"
        )
        assert DEFAULT_LLM_MODEL_POLICY[Feature.SHOPPING_LIST_DESCRIPTION].eval_model == (
            "google/gemini-3.1-flash-lite"
        )
        assert DEFAULT_LLM_MODEL_POLICY[Feature.PANTRY_PURCHASE_DESCRIPTION].production_model == (
            "google/gemini-2.5-flash-lite"
        )
        assert DEFAULT_LLM_MODEL_POLICY[Feature.PANTRY_PURCHASE_DESCRIPTION].eval_model == (
            "google/gemini-3.1-flash-lite"
        )
        assert DEFAULT_LLM_MODEL_POLICY[Feature.RECEIPT_SCAN].production_model == "google/gemini-3.1-flash-lite"
        assert DEFAULT_LLM_MODEL_POLICY[Feature.RECEIPT_SCAN].eval_model == "google/gemini-3.5-flash"
        assert DEFAULT_LLM_MODEL_POLICY[Feature.RECIPE_IMPORT].production_model == "google/gemini-3.1-flash-lite"
        assert DEFAULT_LLM_MODEL_POLICY[Feature.RECIPE_IMPORT].eval_model == "z-ai/glm-5.2"
        assert DEFAULT_LLM_MODEL_POLICY[Feature.MEAL_PLAN_GENERATION].production_model == "google/gemini-3.1-flash-lite"
        assert DEFAULT_LLM_MODEL_POLICY[Feature.MEAL_PLAN_GENERATION].eval_model == "z-ai/glm-5.2"

    def test_invoke_creates_chat_model_for_feature_and_purpose(self) -> None:
        api_key = SecretStr("test-key")
        router = LLMRouter(api_key=api_key)

        with patch("glean.llm.ChatOpenRouter") as mock_cls:
            mock_cls.return_value.with_structured_output.return_value.invoke.return_value = _StructuredTestResponse(
                name="Pantry", values=["milk"]
            )
            response = router.invoke(
                Feature.RECIPE_IMPORT,
                _StructuredTestResponse,
                system="Extract the recipe.",
                user="<html></html>",
                purpose=ModelPurpose.EVAL,
            )

        mock_cls.assert_called_once_with(
            model="z-ai/glm-5.2",
            openrouter_api_key=api_key,
            max_retries=0,
            request_timeout=10_000,
        )
        assert response == _StructuredTestResponse(name="Pantry", values=["milk"])

    def test_invoke_stamps_feature_as_trace_metadata_once(self) -> None:
        api_key = SecretStr("test-key")
        router = LLMRouter(api_key=api_key)

        with patch("glean.llm.ChatOpenRouter") as mock_cls:
            mock_cls.return_value.with_structured_output.return_value.invoke.return_value = _StructuredTestResponse(
                name="Pantry", values=["milk"]
            )
            router.invoke(
                Feature.SHOPPING_LIST_DESCRIPTION, _StructuredTestResponse, system="Parse the list.", user="2 apples"
            )

        mock_cls.return_value.with_structured_output.assert_called_once_with(
            _StructuredTestResponse, method="json_schema"
        )
        mock_cls.return_value.with_structured_output.return_value.invoke.assert_called_once()
        (messages,), kwargs = mock_cls.return_value.with_structured_output.return_value.invoke.call_args
        assert messages == [SystemMessage(content="Parse the list."), HumanMessage(content="2 apples")]
        assert kwargs["config"]["metadata"] == {"feature": Feature.SHOPPING_LIST_DESCRIPTION}

    def test_invoke_sends_text_and_image_parts_as_one_user_message(self) -> None:
        _, messages = _invoke_and_capture(
            LLMRouter(api_key=SecretStr("test-key")),
            system="Scan the receipt.",
            user=["Extract the items.", ImagePart(data=b"\xff\xd8receipt", mime_type="image/jpeg")],
        )

        [system, user] = messages
        assert system == SystemMessage(content="Scan the receipt.")
        assert isinstance(user, HumanMessage)
        assert _without_ids(user.content_blocks) == [
            {"type": "text", "text": "Extract the items."},
            {"type": "image", "base64": base64.b64encode(b"\xff\xd8receipt").decode(), "mime_type": "image/jpeg"},
        ]

    def test_invoke_bounds_the_call_by_timeout_ms(self) -> None:
        chat_open_router, _ = _invoke_and_capture(
            LLMRouter(api_key=SecretStr("test-key")), system="s", user="u", timeout_ms=2_500
        )

        assert chat_open_router.call_args.kwargs["request_timeout"] == 2_500

    def test_invoke_without_timeout_ms_keeps_the_default_timeout(self) -> None:
        chat_open_router, _ = _invoke_and_capture(LLMRouter(api_key=SecretStr("test-key")), system="s", user="u")

        assert chat_open_router.call_args.kwargs["request_timeout"] == 10_000

    def test_from_settings_applies_feature_policy_overrides(self) -> None:
        settings = Settings(
            _env_file=None,
            openrouter_api_key="test-key",
            recipe_api_key="test-recipe_api_key",
            cognito_user_pool_id="test-cognito_user_pool_id",
            cognito_app_client_id="test-cognito_app_client_id",
            s3_receipts_bucket="test-s3_receipts_bucket",
            llm_model_policy_overrides={
                Feature.RECIPE_IMPORT: LLMModelPolicy(
                    production_model="custom/recipe-prod",
                    eval_model="custom/recipe-eval",
                )
            },
        )

        router = LLMRouter.from_settings(settings)

        assert router.model_id_for(Feature.RECIPE_IMPORT) == "custom/recipe-prod"
        assert router.model_id_for(Feature.RECIPE_IMPORT, purpose=ModelPurpose.EVAL) == "custom/recipe-eval"
        assert router.model_id_for(Feature.MEAL_PLAN_GENERATION) == "google/gemini-3.1-flash-lite"

    def test_constructor_applies_partial_policy_overrides(self) -> None:
        router = LLMRouter(
            api_key=SecretStr("test-key"),
            policy_overrides={
                Feature.RECIPE_IMPORT: LLMModelPolicy(
                    production_model="custom/recipe-prod",
                    eval_model="custom/recipe-judge",
                )
            },
        )

        assert router.model_id_for(Feature.RECIPE_IMPORT) == "custom/recipe-prod"
        assert router.model_id_for(Feature.RECIPE_IMPORT, purpose=ModelPurpose.EVAL) == "custom/recipe-judge"
        assert router.model_id_for(Feature.SHOPPING_LIST_DESCRIPTION) == "google/gemini-2.5-flash-lite"

    def test_from_settings_allows_no_policy_overrides(self) -> None:
        settings = Settings(
            _env_file=None,
            openrouter_api_key="test-key",
            recipe_api_key="test-recipe_api_key",
            cognito_user_pool_id="test-cognito_user_pool_id",
            cognito_app_client_id="test-cognito_app_client_id",
            s3_receipts_bucket="test-s3_receipts_bucket",
            llm_model_policy_overrides=None,
        )

        router = LLMRouter.from_settings(settings)

        assert router.model_id_for(Feature.RECEIPT_SCAN) == "google/gemini-3.1-flash-lite"


class TestInvokeStructured:
    def test_invokes_model_with_schema_and_validates_dict_response(self) -> None:
        model = MagicMock()
        model.with_structured_output.return_value.invoke.return_value = {
            "name": "Pantry",
            "values": ["milk", "eggs"],
        }

        response = invoke_structured(
            model,
            _StructuredTestResponse,
            ["message"],
            config={"metadata": {"feature": "shopping-list-description"}},
        )

        assert response == _StructuredTestResponse(name="Pantry", values=["milk", "eggs"])
        model.with_structured_output.assert_called_once_with(_StructuredTestResponse, method="json_schema")
        model.with_structured_output.return_value.invoke.assert_called_once_with(
            ["message"],
            config={"metadata": {"feature": "shopping-list-description"}},
        )

    def test_accepts_already_validated_model_response(self) -> None:
        model = MagicMock()
        model.with_structured_output.return_value.invoke.return_value = _StructuredTestResponse(
            name="Pantry",
            values=["milk", "eggs"],
        )

        response = invoke_structured(model, _StructuredTestResponse, ["message"])

        assert response == _StructuredTestResponse(name="Pantry", values=["milk", "eggs"])

    def test_rejects_malformed_dict_response(self) -> None:
        model = MagicMock()
        model.with_structured_output.return_value.invoke.return_value = {
            "name": "Pantry",
            "values": "milk",
        }

        with pytest.raises(ValidationError):
            invoke_structured(model, _StructuredTestResponse, ["message"])

    def test_rejects_unstructured_text_response(self) -> None:
        model = MagicMock()
        model.with_structured_output.return_value.invoke.return_value = "not structured output"

        with pytest.raises(ValidationError):
            invoke_structured(model, _StructuredTestResponse, ["message"])


def _mock_model_objects(model_ids: list[str]) -> list[MagicMock]:
    return [MagicMock(id=mid) for mid in model_ids]


class TestValidateModel:
    def test_valid_model_passes(self) -> None:
        mock_client = MagicMock()
        mock_client.models.list.return_value.data = _mock_model_objects(
            ["anthropic/claude-sonnet-4.6", "google/gemma-4-26b-a4b-it:free"]
        )
        with patch("glean.llm.OpenRouter", return_value=mock_client):
            validate_model("anthropic/claude-sonnet-4.6", api_key=SecretStr("test-key"))

    def test_unknown_model_raises(self) -> None:
        mock_client = MagicMock()
        mock_client.models.list.return_value.data = _mock_model_objects(["anthropic/claude-sonnet-4.6"])
        with (
            patch("glean.llm.OpenRouter", return_value=mock_client),
            pytest.raises(ValueError, match="Unknown OpenRouter model"),
        ):
            validate_model("nonexistent/model-99", api_key=SecretStr("test-key"))


class _ScriptedChatModel:
    """Stands in for the chat model: each structured call replays one scripted outcome.

    An outcome is an exception to raise, or ``(finish_reason, parsed)``. The finish reason reaches the
    callbacks the caller attached, the way the real OpenRouter model reports it (checked live: ``length`` when
    cut off by ``max_tokens``, ``stop`` otherwise), while the parsed value is returned regardless, as the real
    model returns a truncated reply parsed into a valid, shorter answer.
    """

    def __init__(self, *outcomes: Exception | tuple[str, _StructuredTestResponse]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def with_structured_output(self, *_: Any, **__: Any) -> _ScriptedChatModel:
        return self

    def invoke(self, _messages: Any, config: dict[str, Any] | None = None) -> _StructuredTestResponse:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        finish_reason, parsed = outcome
        reply = LLMResult(
            generations=[
                [ChatGeneration(message=AIMessage(content="{}"), generation_info={"finish_reason": finish_reason})]
            ]
        )
        for handler in (config or {}).get("callbacks", []):
            handler.on_llm_end(reply)
        return parsed


_FULL = _StructuredTestResponse(name="Receipt", values=["a", "b", "c"])
_CUT_SHORT = _StructuredTestResponse(name="Receipt", values=["a"])


class TestInvokeSafeguards:
    @staticmethod
    def _invoke(model: _ScriptedChatModel, monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> _StructuredTestResponse:
        monkeypatch.setattr("glean.llm.create_chat_model", lambda *_, **__: model)
        return LLMRouter(api_key=SecretStr("test-key")).invoke(
            Feature.RECEIPT_SCAN, _StructuredTestResponse, system="s", user="u", **kwargs
        )

    def test_a_reply_cut_off_by_the_token_limit_is_an_error_not_a_short_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        model = _ScriptedChatModel(("length", _CUT_SHORT))

        with pytest.raises(LLMOutputTruncatedError):
            self._invoke(model, monkeypatch)

    def test_a_complete_reply_is_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._invoke(_ScriptedChatModel(("stop", _FULL)), monkeypatch) == _FULL

    def test_a_cut_off_reply_is_asked_again_when_attempts_allow(self, monkeypatch: pytest.MonkeyPatch) -> None:
        model = _ScriptedChatModel(("length", _CUT_SHORT), ("stop", _FULL))

        assert self._invoke(model, monkeypatch, attempts=2) == _FULL
        assert model.calls == 2

    def test_it_gives_up_after_the_allowed_attempts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        model = _ScriptedChatModel(("length", _CUT_SHORT), ("length", _CUT_SHORT), ("stop", _FULL))

        with pytest.raises(LLMOutputTruncatedError):
            self._invoke(model, monkeypatch, attempts=2)
        assert model.calls == 2

    def test_a_dropped_connection_is_asked_again_when_attempts_allow(self, monkeypatch: pytest.MonkeyPatch) -> None:
        model = _ScriptedChatModel(httpx.ConnectError("Connection reset by peer"), ("stop", _FULL))

        assert self._invoke(model, monkeypatch, attempts=2) == _FULL
        assert model.calls == 2

    def test_a_dropped_connection_is_an_error_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        model = _ScriptedChatModel(httpx.ConnectError("Connection reset by peer"), ("stop", _FULL))

        with pytest.raises(httpx.ConnectError):
            self._invoke(model, monkeypatch)
        assert model.calls == 1

    def test_other_errors_are_not_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        model = _ScriptedChatModel(ValueError("bad request"), ("stop", _FULL))

        with pytest.raises(ValueError, match="bad request"):
            self._invoke(model, monkeypatch, attempts=2)
        assert model.calls == 1

    def test_temperature_and_token_limit_are_applied_to_the_model(self) -> None:
        chat_open_router, _ = _invoke_and_capture(
            LLMRouter(api_key=SecretStr("test-key")), system="s", user="u", temperature=0, max_tokens=3_000
        )

        assert chat_open_router.call_args.kwargs["temperature"] == 0
        assert chat_open_router.call_args.kwargs["max_tokens"] == 3_000
