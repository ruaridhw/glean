"""Judge (b): the decision model's `score` question, asked through DecisionClient."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from glean.decisions import DecisionError, DecisionResponseError
from judge_study.features import FEATURES
from judge_study.results import Attempt, Judgement

if TYPE_CHECKING:
    from collections.abc import Callable

    from glean.decisions import DecisionClient
    from judge_study.results import OutputItem

_QUESTION = "quality"


class DecisionJudge:
    def __init__(
        self,
        client: DecisionClient,
        *,
        ledger: list[Attempt] | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._client = client
        self._ledger = ledger if ledger is not None else []
        self._clock = clock

    def judge(self, item: OutputItem, repeat: int) -> Judgement:
        """One call, logged in the ledger whether it works or not."""
        spec = FEATURES[item.feature]
        state = {"evaluation": spec.prompt(**item.judge_inputs)}
        number = 1 + sum((a.judge, a.item_id, a.repeat) == ("decision", item.item_id, repeat) for a in self._ledger)
        started = self._clock()
        try:
            decision = self._client.decide(state, {_QUESTION: spec.question})
            answer = decision.score(_QUESTION)
        except DecisionError as error:
            outcome = "parse_failure" if isinstance(error, DecisionResponseError) else "call_failure"
            self._ledger.append(
                Attempt(
                    judge="decision",
                    item_id=item.item_id,
                    repeat=repeat,
                    attempt=number,
                    outcome=outcome,
                    latency_s=self._clock() - started,
                    error=f"{type(error).__name__}: {str(error)[:150]}",
                )
            )
            raise
        latency = self._clock() - started
        self._ledger.append(
            Attempt(
                judge="decision",
                item_id=item.item_id,
                repeat=repeat,
                attempt=number,
                outcome="ok",
                latency_s=latency,
                input_tokens=decision.usage.input_tokens,
                output_tokens=decision.usage.output_tokens,
                cost_usd=decision.usage.cost,
                cost_basis="reported",
            )
        )
        levels = [answer.probabilities.get(level, 0.0) for level in range(len(spec.question.criteria))]
        return Judgement(
            judge="decision",
            repeat=repeat,
            score=levels.index(max(levels)) + 1,
            model=decision.model,
            latency_s=latency,
            cost_usd=decision.usage.cost,
            cost_basis="reported",
            weighted_score=answer.score + 1,
            confidence=answer.confidence,
            probabilities=levels,
        )
