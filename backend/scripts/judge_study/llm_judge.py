"""Judge (a): today's LLM eval judge, run as the evals run it, with latency and OpenRouter's cost recorded."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx
from langchain_core.callbacks import BaseCallbackHandler

from judge_study.features import FEATURES
from judge_study.results import Judgement

if TYPE_CHECKING:
    from collections.abc import Callable

    from langchain_core.language_models import BaseChatModel
    from langchain_core.outputs import LLMResult

    from judge_study.results import OutputItem

MODELS_URL = "https://openrouter.ai/api/v1/models"


@dataclass(frozen=True)
class Prices:
    """USD per token, as OpenRouter lists them."""

    prompt_per_token: float
    completion_per_token: float


class UsageRecorder(BaseCallbackHandler):
    """Notes the tokens of every call a chat model makes."""

    def __init__(self) -> None:
        self._calls: list[tuple[int, int]] = []

    def on_llm_end(self, response: LLMResult, **_: Any) -> None:
        for generations in response.generations:
            for generation in generations:
                usage = getattr(getattr(generation, "message", None), "usage_metadata", None)
                if usage:
                    self._calls.append((usage["input_tokens"], usage["output_tokens"]))

    def drain(self) -> list[tuple[int, int]]:
        calls, self._calls = self._calls, []
        return calls


def fetch_prices(model_ids: list[str], *, transport: httpx.BaseTransport | None = None) -> dict[str, Prices]:
    """OpenRouter's list prices for the given models. Its generation-stats endpoint doesn't know these calls."""
    listed = httpx.Client(timeout=30.0, transport=transport).get(MODELS_URL).json()["data"]
    by_id = {model["id"]: model["pricing"] for model in listed}
    return {
        model_id: Prices(float(by_id[model_id]["prompt"]), float(by_id[model_id]["completion"]))
        for model_id in model_ids
    }


class LlmJudge:
    def __init__(
        self,
        model: BaseChatModel,
        *,
        model_id: str,
        recorder: UsageRecorder,
        prices: Prices | None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._model = model
        self._model_id = model_id
        self._recorder = recorder
        self._prices = prices
        self._clock = clock

    def judge(self, item: OutputItem, repeat: int) -> Judgement:
        self._recorder.drain()
        started = self._clock()
        score = FEATURES[item.feature].llm_judge(self._model, **item.judge_inputs)
        latency = self._clock() - started
        calls = self._recorder.drain()
        cost = (
            sum(i * self._prices.prompt_per_token + o * self._prices.completion_per_token for i, o in calls)
            if self._prices and calls
            else None
        )
        return Judgement(
            judge="llm",
            repeat=repeat,
            score=score,
            model=self._model_id,
            latency_s=latency,
            cost_usd=cost,
        )
