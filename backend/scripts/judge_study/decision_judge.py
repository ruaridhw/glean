"""Judge (b): the decision model's `score` question, asked through DecisionClient."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from judge_study.features import FEATURES
from judge_study.results import Judgement

if TYPE_CHECKING:
    from collections.abc import Callable

    from glean.decisions import DecisionClient
    from judge_study.results import OutputItem

_QUESTION = "quality"


class DecisionJudge:
    def __init__(self, client: DecisionClient, *, clock: Callable[[], float] = time.perf_counter) -> None:
        self._client = client
        self._clock = clock

    def judge(self, item: OutputItem, repeat: int) -> Judgement:
        spec = FEATURES[item.feature]
        state = {"evaluation": spec.prompt(**item.judge_inputs)}
        started = self._clock()
        decision = self._client.decide(state, {_QUESTION: spec.question})
        latency = self._clock() - started
        answer = decision.score(_QUESTION)
        levels = [answer.probabilities.get(level, 0.0) for level in range(len(spec.question.criteria))]
        return Judgement(
            judge="decision",
            repeat=repeat,
            score=levels.index(max(levels)) + 1,
            model=decision.model,
            latency_s=latency,
            cost_usd=decision.usage.cost,
            weighted_score=answer.score + 1,
            confidence=answer.confidence,
            probabilities=levels,
        )
