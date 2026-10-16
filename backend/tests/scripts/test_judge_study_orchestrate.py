from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from judge_study.decision_judge import DecisionJudge
from judge_study.llm_judge import LlmJudge, Prices, UsageRecorder
from judge_study.orchestrate import run_jobs
from judge_study.report import Narrative, build_report
from judge_study.results import Attempt, OutputItem, Results

from glean.decisions import DecisionClient

if TYPE_CHECKING:
    from collections.abc import Callable

PRICES = Prices(prompt_per_token=1e-6, completion_per_token=5e-6)
ONE_CALL_COST = 1000 * 1e-6 + 200 * 5e-6  # tokens each fake call reports, at PRICES


class _ChatModel:
    """The judge's chat model at the system boundary. It reports its tokens, then either answers or fails to parse."""

    def __init__(self, recorder: UsageRecorder, outcomes: Any) -> None:
        self.callbacks = [recorder]
        self._outcomes = outcomes

    def with_structured_output(self, schema: type, **_: Any) -> _ChatModel:
        self._schema = schema
        return self

    def invoke(self, messages: list[Any], **_: Any) -> Any:
        message = AIMessage(
            content="", usage_metadata={"input_tokens": 1000, "output_tokens": 200, "total_tokens": 1200}
        )
        for handler in self.callbacks:
            handler.on_llm_end(LLMResult(generations=[[ChatGeneration(message=message)]]))
        outcome = next(self._outcomes)
        if outcome == "unparseable":
            raise OutputParserException("Failed to parse JudgeScoreResponse from completion {}")
        return self._schema(score=outcome)


def _item(item_id: str = "recipe_import/0/0") -> OutputItem:
    return OutputItem(
        item_id=item_id,
        feature="recipe_import",
        input={},
        output={},
        judge_inputs={"html_snippet": "<h1>Soup</h1>", "extracted_json": {"title": "Soup"}},
    )


def _results(*items: OutputItem) -> Results:
    return Results(models={}, items=list(items) or [_item()])


def _llm_factory(outcomes: Any, clock: Callable[[], float]) -> Callable[[str, OutputItem, list[Attempt]], LlmJudge]:
    def make(name: str, item: OutputItem, ledger: list[Attempt]) -> LlmJudge:
        recorder = UsageRecorder()
        return LlmJudge(
            _ChatModel(recorder, outcomes),
            model_id="z-ai/glm-5.2",
            recorder=recorder,
            prices=PRICES,
            ledger=ledger,
            clock=clock,
        )

    return make


def _clock(*readings: float) -> Callable[[], float]:
    ticks = iter(readings)
    return lambda: next(ticks)


class TestParseFailureThenSuccess:
    def test_the_judgement_carries_the_cost_and_time_of_every_paid_attempt(self) -> None:
        make = _llm_factory(iter(["unparseable", 4]), _clock(0.0, 1.0, 10.0, 12.5))

        results = run_jobs(_results(), [("recipe_import/0/0", "llm", 1)], make, workers=1)

        (judgement,) = results.items[0].judgements
        assert judgement.score == 4
        assert judgement.attempts == 2
        assert judgement.cost_usd == pytest.approx(2 * ONE_CALL_COST)
        assert judgement.latency_s == pytest.approx(1.0 + 2.5)
        assert judgement.cost_basis == "estimated"
        assert results.failures == []

    def test_the_ledger_keeps_each_attempt_with_its_outcome_tokens_and_cost(self) -> None:
        make = _llm_factory(iter(["unparseable", 4]), _clock(0.0, 1.0, 10.0, 12.5))

        results = run_jobs(_results(), [("recipe_import/0/0", "llm", 1)], make, workers=1)

        first, second = results.attempts
        assert (first.attempt, first.outcome, first.input_tokens, first.output_tokens) == (
            1,
            "parse_failure",
            1000,
            200,
        )
        assert first.cost_usd == pytest.approx(ONE_CALL_COST)
        assert first.latency_s == pytest.approx(1.0)
        assert (second.attempt, second.outcome) == (2, "ok")


class TestFailedJobs:
    def _failing(self, tmp_path: Path) -> Results:
        make = _llm_factory(iter(["unparseable", "unparseable"]), _clock(0.0, 1.0, 2.0, 3.0))
        results = run_jobs(_results(), [("recipe_import/0/0", "llm", 1)], make, workers=1)
        results.save(tmp_path / "results.json")
        return Results.load(tmp_path / "results.json")

    def test_a_job_that_fails_every_attempt_is_a_typed_failure_that_survives_save_and_load(
        self, tmp_path: Path
    ) -> None:
        reloaded = self._failing(tmp_path)

        (failure,) = reloaded.failures
        assert (failure.judge, failure.item_id, failure.repeat) == ("llm", "recipe_import/0/0", 1)
        assert "OutputParserException" in failure.error
        assert reloaded.items[0].judgements == []

    def test_both_paid_attempts_stay_in_the_ledger_even_though_nothing_was_obtained(self, tmp_path: Path) -> None:
        reloaded = self._failing(tmp_path)

        assert [a.outcome for a in reloaded.attempts] == ["parse_failure", "parse_failure"]
        assert sum(a.cost_usd or 0 for a in reloaded.attempts) == pytest.approx(2 * ONE_CALL_COST)

    def test_the_report_still_renders_and_counts_attempts_parse_failures_and_failed_jobs_separately(
        self, tmp_path: Path
    ) -> None:
        page = build_report(self._failing(tmp_path), Narrative(verdict="v", recommendation="r", notes=[]))

        operations = page[page.index('id="operations"') :]
        assert "Attempted calls" in operations
        assert "Parse failures" in operations
        assert "Final failed jobs" in operations

    def test_a_later_run_picks_the_failed_job_up_and_clears_its_failure(self, tmp_path: Path) -> None:
        failed = self._failing(tmp_path)
        make = _llm_factory(iter([5]), _clock(20.0, 21.0))

        resumed = run_jobs(failed, [("recipe_import/0/0", "llm", 1)], make, workers=1)

        assert [j.score for j in resumed.items[0].judgements] == [5]
        assert resumed.failures == []
        assert len(resumed.attempts) == 3

    def test_a_recovered_job_keeps_the_cost_time_and_numbering_of_its_earlier_attempts(self, tmp_path: Path) -> None:
        failed = self._failing(tmp_path)  # two failed calls: 1 s each, one call's cost each
        make = _llm_factory(iter([5]), _clock(20.0, 21.0))

        resumed = run_jobs(failed, [("recipe_import/0/0", "llm", 1)], make, workers=1)

        (judgement,) = resumed.items[0].judgements
        assert judgement.attempts == 3
        assert judgement.cost_usd == pytest.approx(3 * ONE_CALL_COST)
        assert judgement.latency_s == pytest.approx(3.0)
        assert [a.attempt for a in resumed.attempts] == [1, 2, 3]
        page = build_report(resumed, Narrative(verdict="v", recommendation="r", notes=[]))
        assert f"${3 * ONE_CALL_COST:.3f}" in page[page.index('id="operations"') :]

    def test_the_spend_cap_counts_only_the_calls_of_the_current_run(self, tmp_path: Path) -> None:
        failed = self._failing(tmp_path)  # already spent 2 * ONE_CALL_COST in an earlier run
        make = _llm_factory(iter([5]), _clock(20.0, 21.0))

        resumed = run_jobs(failed, [("recipe_import/0/0", "llm", 1)], make, workers=1, spend_cap=ONE_CALL_COST / 2)

        assert len(resumed.items[0].judgements) == 1

    def test_a_judgement_already_obtained_is_not_paid_for_again(self) -> None:
        make = _llm_factory(iter([4]), _clock(0.0, 1.0))
        first = run_jobs(_results(), [("recipe_import/0/0", "llm", 1)], make, workers=1)

        def never(*_: Any) -> Any:
            raise AssertionError("asked again for a judgement that exists")

        again = run_jobs(first, [("recipe_import/0/0", "llm", 1)], never, workers=1)

        assert len(again.items[0].judgements) == 1


class TestDecisionEndpointFailures:
    def _make(self, handler: Callable[[httpx.Request], httpx.Response]) -> Callable[..., DecisionJudge]:
        client = DecisionClient(api_key=SecretStr("sk-or-test"), transport=httpx.MockTransport(handler))

        def make(name: str, item: OutputItem, ledger: list[Attempt]) -> DecisionJudge:
            return DecisionJudge(client, ledger=ledger)

        return make

    def test_an_http_error_is_a_failed_job_and_its_unpriced_attempts_are_not_given_a_cost_of_zero(self) -> None:
        make = self._make(lambda _: httpx.Response(500, text="boom"))

        results = run_jobs(_results(), [("recipe_import/0/0", "decision", 1)], make, workers=1)

        (failure,) = results.failures
        assert failure.judge == "decision"
        assert "DecisionHTTPError" in failure.error
        assert [a.outcome for a in results.attempts] == ["call_failure", "call_failure"]
        assert all(a.cost_usd is None and a.input_tokens is None for a in results.attempts)

    def test_an_answer_that_breaks_the_question_is_a_parse_failure_not_a_call_failure(self) -> None:
        make = self._make(lambda _: httpx.Response(200, json={"answers": {}}))

        results = run_jobs(_results(), [("recipe_import/0/0", "decision", 1)], make, workers=1)

        assert [a.outcome for a in results.attempts] == ["parse_failure", "parse_failure"]

    def test_a_successful_answer_records_the_endpoints_own_cost_and_tokens(self) -> None:
        body = {
            "model": "typesafe/jev-1.14-20261014",
            "id": "gen-dec-1",
            "provider": "TypeSafe",
            "answers": {
                "quality": {
                    "type": "score",
                    "score": 3.0,
                    "probabilities": {"0": 0, "1": 0, "2": 0, "3": 0, "4": 1},
                    "confidence": 0.9,
                }
            },
            "usage": {"input_tokens": 400, "output_tokens": 50, "cost": 1.7e-5},
        }
        make = self._make(lambda _: httpx.Response(200, json=body))

        results = run_jobs(_results(), [("recipe_import/0/0", "decision", 1)], make, workers=1)

        (attempt,) = results.attempts
        assert (attempt.outcome, attempt.input_tokens, attempt.output_tokens) == ("ok", 400, 50)
        assert attempt.cost_usd == pytest.approx(1.7e-5)
        assert attempt.cost_basis == "reported"
        assert results.items[0].judgements[0].cost_basis == "reported"


class TestUnknownCosts:
    def _flaky(self, statuses: list[int]) -> Callable[..., DecisionJudge]:
        replies = iter(statuses)
        ok = {
            "model": "typesafe/jev-1.14-20261014",
            "id": "gen-dec-1",
            "provider": "TypeSafe",
            "answers": {
                "quality": {
                    "type": "score",
                    "score": 3.0,
                    "probabilities": {"0": 0, "1": 0, "2": 0, "3": 0, "4": 1},
                    "confidence": 0.9,
                }
            },
            "usage": {"input_tokens": 400, "output_tokens": 50, "cost": 0.001},
        }

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=ok) if next(replies) == 200 else httpx.Response(500, text="boom")

        client = DecisionClient(api_key=SecretStr("sk-or-test"), transport=httpx.MockTransport(handler))
        return lambda name, item, ledger: DecisionJudge(client, ledger=ledger)

    def test_a_judgement_whose_earlier_call_was_unpriced_is_marked_as_a_lower_bound(self) -> None:
        results = run_jobs(_results(), [("recipe_import/0/0", "decision", 1)], self._flaky([500, 200]), workers=1)

        (judgement,) = results.items[0].judgements
        assert (judgement.cost_usd, judgement.unpriced_attempts, judgement.attempts) == (0.001, 1, 2)

    def test_the_report_gives_a_known_subtotal_and_the_unpriced_count_not_a_complete_looking_total(self) -> None:
        results = run_jobs(_results(), [("recipe_import/0/0", "decision", 1)], self._flaky([500, 200]), workers=1)

        operations = _operations_of(results)

        assert "$0.001 known + 1 unpriced call" in operations
        assert "unknown (1 incomplete)" in operations  # no full-cost mean can be claimed

    def test_when_nothing_could_be_priced_the_report_says_unknown_not_zero(self) -> None:
        results = run_jobs(_results(), [("recipe_import/0/0", "decision", 1)], self._flaky([500, 500]), workers=1)

        operations = _operations_of(results)

        assert "unknown" in operations
        assert "$0 " not in operations
        assert "$0<" not in operations

    def test_unpriced_calls_count_against_the_spend_cap_at_a_conservative_assumed_cost(self) -> None:
        results = _results(_item("recipe_import/0/0"), _item("recipe_import/1/0"))
        jobs = [(item.item_id, "decision", 1) for item in results.items]

        done = run_jobs(results, jobs, self._flaky([500] * 8), workers=1, spend_cap=0.015, unpriced_call_cost=0.01)

        # Two unpriced calls assume $0.02, which reaches the cap, so the second job never starts.
        assert len(done.attempts) == 2


def _operations_of(results: Results) -> str:
    page = build_report(results, Narrative(verdict="v", recommendation="r", notes=[]))
    return page[page.index('id="operations"') : page.index('id="recommendation"')]


class TestSpendCap:
    def test_no_new_job_starts_once_the_attempts_so_far_have_reached_the_cap(self) -> None:
        make = _llm_factory(iter([4, 4, 4]), _clock(*range(10)))
        results = _results(_item("recipe_import/0/0"), _item("recipe_import/1/0"), _item("recipe_import/2/0"))
        jobs = [(item.item_id, "llm", 1) for item in results.items]

        done = run_jobs(results, jobs, make, workers=1, spend_cap=ONE_CALL_COST * 1.5)

        assert sum(len(item.judgements) for item in done.items) == 2  # the second call crosses the cap
