from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from judge_study.llm_judge import LlmJudge, UsageRecorder, generation_cost_lookup
from judge_study.results import OutputItem


class _ChatModel:
    """The judge's chat model at the system boundary: answers a score and reports its generation, as OpenRouter does."""

    def __init__(self, recorder: UsageRecorder, score: int, generation_id: str = "gen-1") -> None:
        self.callbacks = [recorder]
        self._score = score
        self._generation_id = generation_id

    def with_structured_output(self, schema: type, **_: Any) -> _ChatModel:
        self._schema = schema
        return self

    def invoke(self, messages: list[Any], **_: Any) -> Any:
        message = AIMessage(content="", response_metadata={"id": self._generation_id})
        for handler in self.callbacks:
            handler.on_llm_end(LLMResult(generations=[[ChatGeneration(message=message)]]))
        return self._schema(score=self._score)


def _item() -> OutputItem:
    return OutputItem(
        item_id="recipe_import/0/0",
        feature="recipe_import",
        input={},
        output={},
        judge_inputs={"html_snippet": "<h1>Soup</h1>", "extracted_json": {"title": "Soup"}},
    )


def _judge(score: int, costs: dict[str, float | None], clock: Any = None) -> LlmJudge:
    recorder = UsageRecorder()
    return LlmJudge(
        _ChatModel(recorder, score),
        model_id="google/gemini-3.1-flash-lite",
        recorder=recorder,
        cost_of=costs.get,
        clock=clock or iter([1.0, 3.5]).__next__,
    )


class TestLlmJudge:
    def test_it_returns_the_score_the_existing_judge_function_gives(self) -> None:
        judgement = _judge(4, {"gen-1": 0.0004}).judge(_item(), repeat=3)

        assert (judgement.judge, judgement.repeat, judgement.score) == ("llm", 3, 4)
        assert judgement.model == "google/gemini-3.1-flash-lite"

    def test_latency_and_openrouters_cost_for_the_generation_are_recorded(self) -> None:
        judgement = _judge(5, {"gen-1": 0.0004}).judge(_item(), repeat=1)

        assert judgement.latency_s == pytest.approx(2.5)
        assert judgement.cost_usd == pytest.approx(0.0004)

    def test_an_unreported_cost_is_recorded_as_unknown_not_zero(self) -> None:
        assert _judge(3, {"gen-1": None}).judge(_item(), repeat=1).cost_usd is None


class TestGenerationCostLookup:
    def test_it_reads_the_total_cost_openrouter_reports_for_a_generation(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.params["id"] == "gen-9"
            assert request.headers["Authorization"] == "Bearer sk-or-test"
            return httpx.Response(200, json={"data": {"total_cost": 0.00123}})

        lookup = generation_cost_lookup("sk-or-test", transport=httpx.MockTransport(handler), sleep=lambda _: None)

        assert lookup("gen-9") == pytest.approx(0.00123)

    def test_it_waits_for_a_generation_that_is_not_yet_listed(self) -> None:
        replies = iter(
            [httpx.Response(404), httpx.Response(404), httpx.Response(200, json={"data": {"total_cost": 0.5}})]
        )
        waits: list[float] = []

        lookup = generation_cost_lookup("k", transport=httpx.MockTransport(lambda _: next(replies)), sleep=waits.append)

        assert lookup("gen-1") == 0.5
        assert len(waits) == 2

    def test_it_gives_up_with_none_when_the_cost_never_appears(self) -> None:
        lookup = generation_cost_lookup(
            "k", transport=httpx.MockTransport(lambda _: httpx.Response(404)), sleep=lambda _: None, attempts=3
        )

        assert lookup("gen-1") is None
