"""Judge (a): today's LLM eval judge, run as the evals run it, with latency and OpenRouter's cost recorded."""

from __future__ import annotations

import time
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

GENERATION_URL = "https://openrouter.ai/api/v1/generation"


class UsageRecorder(BaseCallbackHandler):
    """Notes the OpenRouter generation id of every call a chat model makes."""

    def __init__(self) -> None:
        self._generation_ids: list[str] = []

    def on_llm_end(self, response: LLMResult, **_: Any) -> None:
        for generations in response.generations:
            for generation in generations:
                metadata = getattr(getattr(generation, "message", None), "response_metadata", {}) or {}
                if "id" in metadata:
                    self._generation_ids.append(metadata["id"])

    def drain(self) -> list[str]:
        ids, self._generation_ids = self._generation_ids, []
        return ids


def generation_cost_lookup(
    api_key: str,
    *,
    transport: httpx.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
    attempts: int = 6,
) -> Callable[[str], float | None]:
    """Cost in USD that OpenRouter reports for a generation, which it lists a moment after the call."""
    http = httpx.Client(headers={"Authorization": f"Bearer {api_key}"}, timeout=20.0, transport=transport)

    def cost_of(generation_id: str) -> float | None:
        for attempt in range(attempts):
            response = http.get(GENERATION_URL, params={"id": generation_id})
            if response.is_success:
                cost = response.json().get("data", {}).get("total_cost")
                return None if cost is None else float(cost)
            if attempt < attempts - 1:
                sleep(1.5)
        return None

    return cost_of


class LlmJudge:
    def __init__(
        self,
        model: BaseChatModel,
        *,
        model_id: str,
        recorder: UsageRecorder,
        cost_of: Callable[[str], float | None],
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._model = model
        self._model_id = model_id
        self._recorder = recorder
        self._cost_of = cost_of
        self._clock = clock

    def judge(self, item: OutputItem, repeat: int) -> Judgement:
        self._recorder.drain()
        started = self._clock()
        score = FEATURES[item.feature].llm_judge(self._model, **item.judge_inputs)
        latency = self._clock() - started
        costs = [self._cost_of(generation_id) for generation_id in self._recorder.drain()]
        known = [cost for cost in costs if cost is not None]
        return Judgement(
            judge="llm",
            repeat=repeat,
            score=score,
            model=self._model_id,
            latency_s=latency,
            cost_usd=sum(known) if known and len(known) == len(costs) else None,
        )
