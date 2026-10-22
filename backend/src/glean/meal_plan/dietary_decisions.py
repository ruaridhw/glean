"""Dietary decisions: stored beside the corpus, read when candidates are chosen.

Generate never calls the decision model. A producer — now the enrichment runner (`recipes/enrichment/`)
rather than a script of its own — computes one probability per (recipe, flag), stores them as decision
answers in the corpus store, and candidate selection reads them back. The decision is the only dietary
rule: there are no ingredient word lists behind it.

This module is the **read side**. The questions, their wording and their thresholds live with the enricher
that asks them (`recipes.enrichment.dietary`, ADR 0025) and are re-exported here so the audit script, the
tests and callers keep one obvious place to look.

An answer is stored under the stable question name `dietary:<flag>` (see `recipes.answers`), so it lands in
the DynamoDB ANSWER item or the pre-F1 JSONL line without the two stores needing different shapes.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - pydantic resolves the field type at runtime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from glean.recipes.answers import (
    DIETARY_DECISIONS_KEY,
    RecipeAnswer,
    content_fingerprint,
    dietary_flag,
    dietary_question,
)
from glean.recipes.enrichment.dietary import (
    DIETARY_FLAGS,
    PEANUT_FREE,
    PEANUT_FREE_THRESHOLD,
    PREFERENCE_THRESHOLD,
    THRESHOLDS,
    TREE_NUT_FREE,
    TREE_NUT_FREE_THRESHOLD,
    dietary_enrichment_question,
    dietary_questions,
)
from glean.recipes.enrichment.enricher import is_current_model, question_hash
from glean.recipes.enrichment.runner import CorpusUnavailableError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from glean.recipes.corpus import CorpusBackend
    from glean.recipes.search_index import RecipeSummary

__all__ = [
    "DIETARY_DECISIONS_KEY",
    "DIETARY_FLAGS",
    "LEGACY_NUT_FREE",
    "PEANUT_FREE",
    "PEANUT_FREE_THRESHOLD",
    "PREFERENCE_THRESHOLD",
    "THRESHOLDS",
    "TREE_NUT_FREE",
    "TREE_NUT_FREE_THRESHOLD",
    "CorpusUnavailableError",
    "DietaryDecision",
    "DietaryDecisionStore",
    "DietaryDecisions",
    "content_fingerprint",
    "dietary_answers",
    "dietary_questions",
    "question_hash",
]

# Spelled by older app builds, which had one nut flag. It stands for both allergies.
LEGACY_NUT_FREE = "nut-free"


class DietaryDecision(BaseModel):
    """The model's probability that a recipe breaks a dietary flag, with what produced it."""

    recipe_id: str = Field(description="External id of the corpus recipe that was assessed.")
    flag: str = Field(description="Normalised dietary flag the question was about, e.g. nut-free.")
    probability: float = Field(ge=0.0, le=1.0, description="Probability that the recipe breaks the flag.")
    model: str = Field(description="Dated snapshot of the decision model that answered.")
    content_hash: str = Field(description="`content_fingerprint` of the recipe state (title, ingredients) assessed.")
    criteria_hash: str = Field(
        description="`question_hash` of the flag's question (instructions, criteria) it answered."
    )
    computed_at: datetime = Field(description="When the decision was computed.")


class DietaryDecisionStore:
    """Dietary decisions as corpus answers: one per (recipe, flag), through whichever backend is open."""

    def __init__(self, corpus: CorpusBackend) -> None:
        self._corpus = corpus

    def load(self) -> list[DietaryDecision]:
        """Every stored dietary decision, in whatever order the store returns the answers.

        A (recipe, flag) can carry more than one — a reworded question leaves its old answer beside the new
        one — and `DietaryDecisions` is what decides which of them speaks for the recipe. That selection
        lives there and only there, so the blob JSONL, the table and a rebuilt projection all agree.
        """
        return [
            _decision_from_answer(answer)
            for answer in self._corpus.answers()
            if dietary_flag(answer.question) is not None
        ]

    def save(self, decisions: list[DietaryDecision]) -> None:
        self._corpus.save_answers(dietary_answers(decisions))


def dietary_answers(decisions: Iterable[DietaryDecision]) -> list[RecipeAnswer]:
    """The stored answers that carry these decisions, for a producer writing them as corpus data."""
    return [_answer_from_decision(decision) for decision in decisions]


def _answer_from_decision(decision: DietaryDecision) -> RecipeAnswer:
    return RecipeAnswer(
        recipe_id=decision.recipe_id,
        question=dietary_question(decision.flag),
        probability=decision.probability,
        model=decision.model,
        content_hash=decision.content_hash,
        criteria_hash=decision.criteria_hash,
        computed_at=decision.computed_at,
    )


def _decision_from_answer(answer: RecipeAnswer) -> DietaryDecision:
    """The dietary decision a stored answer carries. Only called for answers naming a dietary question."""
    flag = dietary_flag(answer.question)
    assert flag is not None  # noqa: S101 - the caller filtered on exactly this
    return DietaryDecision(
        recipe_id=answer.recipe_id,
        flag=flag,
        probability=answer.probability,
        model=answer.model,
        content_hash=answer.content_hash,
        criteria_hash=answer.criteria_hash,
        computed_at=answer.computed_at,
    )


class DietaryDecisions:
    """Stored decisions, looked up by (recipe id, flag).

    A (recipe, flag) can have several stored answers: the table keys them by criteria hash, and a reworded
    question leaves the old wording's answer beside the new one. Keep the one that speaks for what is asked
    now — an older wording can never shadow it — and among equals the latest computation wins. The corpus
    answers, the blob JSONL and a projection rebuilt from the table all go through this.
    """

    def __init__(self, decisions: list[DietaryDecision]) -> None:
        self._by_key: dict[tuple[str, str], DietaryDecision] = {}
        for decision in decisions:
            key = (decision.recipe_id, decision.flag)
            incumbent = self._by_key.get(key)
            if incumbent is None or _preferred(decision, incumbent):
                self._by_key[key] = decision

    def excludes(self, summary: RecipeSummary, flag: str) -> bool:
        """Whether a stored decision rules the recipe out under `flag` (a normalised flag name).

        A recipe with no current decision is excluded under every flag the model is asked about:
        with no ingredient rules to fall back on, an unanswered question can't be assumed safe.
        The legacy `nut-free` an older app build sends stands for tree-nut-free and peanut-free together.
        """
        if flag == LEGACY_NUT_FREE:
            return self.excludes(summary, TREE_NUT_FREE) or self.excludes(summary, PEANUT_FREE)
        if flag not in DIETARY_FLAGS:
            return False
        decision = self._by_key.get((summary.external_id, flag))
        if decision is None or not _is_current(decision, summary):
            return True
        return decision.probability >= THRESHOLDS.get(flag, PREFERENCE_THRESHOLD)


def _preferred(candidate: DietaryDecision, incumbent: DietaryDecision) -> bool:
    """Whether `candidate` speaks for the current question better than `incumbent`."""
    if _answers_current_question(candidate) != _answers_current_question(incumbent):
        return _answers_current_question(candidate)
    return (candidate.computed_at, candidate.criteria_hash) > (incumbent.computed_at, incumbent.criteria_hash)


def _answers_current_question(decision: DietaryDecision) -> bool:
    question = dietary_enrichment_question(decision.flag)
    return (
        question is not None and decision.criteria_hash == question.criteria_hash and is_current_model(decision.model)
    )


def _is_current(decision: DietaryDecision, summary: RecipeSummary) -> bool:
    # Thresholds are calibrated to one model version (`model` is the model's dated snapshot of it) and to the
    # criteria text; a decision only speaks for the title and ingredients it was asked about.
    # A flag that is no longer asked about (the old nut-free) can't be current, whatever it was computed under.
    question = dietary_enrichment_question(decision.flag)
    return (
        question is not None
        and is_current_model(decision.model)
        and decision.content_hash == content_fingerprint(summary.title, summary.ingredient_names)
        and decision.criteria_hash == question.criteria_hash
    )
