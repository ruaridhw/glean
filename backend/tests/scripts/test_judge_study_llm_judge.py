from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from judge_study.llm_judge import LlmJudge, Prices, UsageRecorder, fetch_prices
from judge_study.results import OutputItem


class _ChatModel:
    """The judge's chat model at the system boundary: answers a score and reports token usage."""

    def __init__(self, recorder: UsageRecorder, score: int) -> None:
        self.callbacks = [recorder]
        self._score = score

    def with_structured_output(self, schema: type, **_: Any) -> _ChatModel:
        self._schema = schema
        return self

    def invoke(self, messages: list[Any], **_: Any) -> Any:
        message = AIMessage(
            content="", usage_metadata={"input_tokens": 1000, "output_tokens": 200, "total_tokens": 1200}
        )
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


PRICES = Prices(prompt_per_token=1e-6, completion_per_token=5e-6)


def _judge(score: int, prices: Prices | None = PRICES, clock: Any = None) -> LlmJudge:
    recorder = UsageRecorder()
    return LlmJudge(
        _ChatModel(recorder, score),
        model_id="google/gemini-3.1-flash-lite",
        recorder=recorder,
        prices=prices,
        clock=clock or iter([1.0, 3.5]).__next__,
    )


class TestLlmJudge:
    def test_it_returns_the_score_the_existing_judge_function_gives(self) -> None:
        judgement = _judge(4).judge(_item(), repeat=3)

        assert (judgement.judge, judgement.repeat, judgement.score) == ("llm", 3, 4)
        assert judgement.model == "google/gemini-3.1-flash-lite"

    def test_a_panel_judge_is_the_same_judge_under_its_own_name(self) -> None:
        recorder = UsageRecorder()
        panel = LlmJudge(
            _ChatModel(recorder, 3),
            model_id="anthropic/claude-sonnet-5.5",
            recorder=recorder,
            prices=PRICES,
            judge_name="panel_claude",
        )

        judgement = panel.judge(_item(), repeat=1)

        assert (judgement.judge, judgement.model, judgement.score) == ("panel_claude", "anthropic/claude-sonnet-5.5", 3)

    def test_latency_and_the_cost_of_the_tokens_used_are_recorded(self) -> None:
        judgement = _judge(5).judge(_item(), repeat=1)

        assert judgement.latency_s == pytest.approx(2.5)
        assert judgement.cost_usd == pytest.approx(1000 * 1e-6 + 200 * 5e-6)

    def test_without_prices_the_cost_is_unknown_not_zero(self) -> None:
        assert _judge(3, prices=None).judge(_item(), repeat=1).cost_usd is None


class TestListPrices:
    def test_prices_come_from_openrouters_model_list_per_token(self) -> None:
        body = {
            "data": [
                {"id": "a/x", "pricing": {"prompt": "0.0000015", "completion": "0.000009"}},
                {"id": "b/y", "pricing": {"prompt": "0", "completion": "0"}},
            ]
        }

        prices = fetch_prices(["a/x"], transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)))

        assert prices == {"a/x": Prices(prompt_per_token=1.5e-6, completion_per_token=9e-6)}

    def test_a_model_missing_from_the_list_is_an_error_not_a_free_judge(self) -> None:
        transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"data": []}))

        with pytest.raises(KeyError, match="a/x"):
            fetch_prices(["a/x"], transport=transport)
