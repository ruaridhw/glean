from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import SecretStr

from glean.llm import Feature, LLMRouter
from tests.integration.evals.conftest import _eval_model_id_for, _judge_model_id_for

if TYPE_CHECKING:
    import pytest


class TestEvalModelPolicy:
    def test_eval_model_defaults_to_feature_production_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GLEAN_EVAL_MODEL", raising=False)
        router = LLMRouter(api_key=SecretStr("test-key"))

        model_id = _eval_model_id_for(Feature.RECIPE_IMPORT, router)

        assert model_id == "qwen/qwen3.7-plus"

    def test_judge_model_defaults_to_feature_eval_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GLEAN_JUDGE_MODEL", raising=False)
        router = LLMRouter(api_key=SecretStr("test-key"))

        model_id = _judge_model_id_for(Feature.RECIPE_IMPORT, router)

        assert model_id == "z-ai/glm-5.2"

    def test_global_emergency_overrides_are_kept_separate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        router = LLMRouter(api_key=SecretStr("test-key"))
        monkeypatch.setenv("GLEAN_EVAL_MODEL", "custom/eval-emergency")
        monkeypatch.setenv("GLEAN_JUDGE_MODEL", "custom/judge-emergency")

        eval_model_id = _eval_model_id_for(Feature.SHOPPING_LIST_DESCRIPTION, router)
        judge_model_id = _judge_model_id_for(Feature.SHOPPING_LIST_DESCRIPTION, router)

        assert eval_model_id == "custom/eval-emergency"
        assert judge_model_id == "custom/judge-emergency"
