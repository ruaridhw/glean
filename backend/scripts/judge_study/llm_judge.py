"""Judge (a): today's LLM eval judge, run as the evals run it, with latency and OpenRouter's cost recorded."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import httpx
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from judge_study.features import FEATURES
from judge_study.results import Attempt, Judgement

if TYPE_CHECKING:
    from collections.abc import Callable

    from langchain_core.language_models import BaseChatModel
    from langchain_core.outputs import LLMResult

    from judge_study.results import JudgeName, OutputItem

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
        judge_name: JudgeName = "llm",
        ledger: list[Attempt] | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._model = model
        self._model_id = model_id
        self._recorder = recorder
        self._prices = prices
        self._judge_name = judge_name
        self._ledger = ledger if ledger is not None else []
        self._clock = clock

    def judge(self, item: OutputItem, repeat: int) -> Judgement:
        """One call. It is logged in the ledger whether it works or not, because a failed call is still paid for."""
        self._recorder.drain()
        started = self._clock()
        error: Exception | None = None
        score = 0
        try:
            score = FEATURES[item.feature].llm_judge(self._model, **item.judge_inputs)
        except Exception as caught:
            error = caught
        latency = self._clock() - started
        calls = self._recorder.drain()
        input_tokens = sum(i for i, _ in calls) if calls else None
        output_tokens = sum(o for _, o in calls) if calls else None
        cost = (
            sum(i * self._prices.prompt_per_token + o * self._prices.completion_per_token for i, o in calls)
            if self._prices and calls
            else None
        )
        number = 1 + sum(
            (a.judge, a.item_id, a.repeat) == (self._judge_name, item.item_id, repeat) for a in self._ledger
        )
        self._ledger.append(
            Attempt(
                judge=self._judge_name,
                item_id=item.item_id,
                repeat=repeat,
                attempt=number,
                outcome="ok" if error is None else _outcome(error),
                latency_s=latency,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                cost_basis="estimated" if cost is not None else None,
                error=None if error is None else f"{type(error).__name__}: {str(error)[:150]}",
            )
        )
        if error is not None:
            raise error
        return Judgement(
            judge=self._judge_name,
            repeat=repeat,
            score=score,
            model=self._model_id,
            latency_s=latency,
            cost_usd=cost,
            cost_basis="estimated" if cost is not None else None,
        )


def _outcome(error: Exception) -> Literal["parse_failure", "call_failure"]:
    """An answer that couldn't be used is a parse failure; no answer at all is a call failure."""
    return "parse_failure" if isinstance(error, OutputParserException | ValidationError) else "call_failure"
