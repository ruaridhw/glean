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

import math
from dataclasses import dataclass
from datetime import datetime  # noqa: TC003 - pydantic resolves the field type at runtime
from types import MappingProxyType
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from glean.decisions import DEFAULT_MODEL, DecisionModel
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
from glean.recipes.enrichment.enricher import question_hash
from glean.recipes.enrichment.runner import CorpusUnavailableError

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from glean.recipes.corpus import CorpusBackend
    from glean.recipes.search_index import RecipeSummary

__all__ = [
    "CALIBRATED_DIETARY",
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
    "DietaryCalibration",
    "DietaryDecision",
    "DietaryDecisionStore",
    "DietaryDecisions",
    "UncalibratedModelError",
    "content_fingerprint",
    "dietary_answers",
    "dietary_questions",
    "question_hash",
]

# Spelled by older app builds, which had one nut flag. It stands for both allergies.
LEGACY_NUT_FREE = "nut-free"

# Thresholds, model identity and their provenance live together: a flag's cutoff is only meaningful for the
# model it was measured against, so the two are one reviewed value rather than separate constants.
_CALIBRATION_EVIDENCE = """
Set from the labelled samples (tests/fixtures/decisions/dietary_sample.json, 63 rows, and dietary_regex_coverage.json,
182 recipes) answered by typesafe/jev-1.14-20261014 on 2026-10-16 under the criteria below, and checked against all
632 prod-corpus recipes. Ground truth there is the retailer's ingredient lists, then the maintainer's labels, then
two judges and the old regex in agreement:
  tree-nut-free: 41 recipes break it, every one scored >= 0.95; 1 of 570 clean recipes scores >= 0.3 (0.84)
  peanut-free:   36 recipes break it, every one scored >= 0.86; 1 of 576 clean recipes scores >= 0.3 (0.44)
Both thresholds start from the 0.3 the single nut flag used and miss nothing on the corpus; 0.3 sits 0.65 (tree)
and 0.56 (peanut) below the lowest violator. On the samples tree-nut-free is clean to 0.11 (a bare korma paste);
peanut-free scores dukkah 0.45, praline 0.35 and a bare chilli crisp 0.33 clean-labelled, which it excludes.
Only nuts in the ingredients count: a "may contain nuts" warning is ignored, and korma, tikka masala and pasanda
pastes are not special (a tree nut is listed in 0 of 9 korma and 1 of 7 tikka masala pastes sold).
Preferences sit between the clusters: 0.12 above the highest clean recipe (gluten-free), 0.27 below the
lowest violator (gluten-free). 0.50 rather than higher because the gluten-free recipe `rec_d1cddd00fba23e5a`
of the prod corpus scores 0.52 and must be excluded.
"""


class UncalibratedModelError(Exception):
    """A client or an answer names a model the dietary calibration doesn't cover, so nothing may decide on it."""


@dataclass(frozen=True, slots=True)
class DietaryCalibration:
    """The model whose probabilities the dietary cutoffs were measured on, and the cutoffs themselves.

    `evidence` records what the thresholds were measured against. It is provenance, not proof: a
    substitution needs its own measurement at its own cutoffs before this value names it.
    """

    model: DecisionModel
    thresholds: Mapping[str, float]
    default_threshold: float
    evidence: str

    def __post_init__(self) -> None:
        # A cutoff only rules a recipe in or out for the flags the model is asked about, and only when it is
        # a real probability: NaN or a value past 1 would silently admit everything.
        unknown = sorted(set(self.thresholds) - set(DIETARY_FLAGS))
        if unknown:
            raise ValueError(f"Thresholds for flags the decision model is not asked about: {unknown}")
        for name, cutoff in (("default", self.default_threshold), *self.thresholds.items()):
            if not math.isfinite(cutoff) or not 0.0 < cutoff < 1.0:
                raise ValueError(f"The {name} cutoff must be a finite number between 0 and 1, not {cutoff!r}")
        if not self.evidence.strip():
            raise ValueError("A calibration needs evidence for its cutoffs, not a blank string")
        # Own the cutoffs: a caller's dict must not be able to change what an existing calibration decides.
        object.__setattr__(self, "thresholds", MappingProxyType(dict(self.thresholds)))

    def threshold_for(self, flag: str) -> float:
        return self.thresholds.get(flag, self.default_threshold)

    def served_identity(self, model: str) -> str:
        """The identity a decision may be recorded under, refused unless this calibration covers the model."""
        if not self.model.accepts(model):
            raise UncalibratedModelError(
                f"The endpoint answered as {model!r}, which the {self.model.request!r} calibration does not cover"
            )
        return model


CALIBRATED_DIETARY = DietaryCalibration(
    model=DEFAULT_MODEL,
    # Exclude when the probability that the recipe breaks the flag reaches the threshold.
    thresholds=MappingProxyType(dict(THRESHOLDS)),
    default_threshold=PREFERENCE_THRESHOLD,
    evidence=_CALIBRATION_EVIDENCE,
)


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

    def __init__(self, decisions: list[DietaryDecision], *, calibration: DietaryCalibration) -> None:
        self._calibration = calibration
        self._by_key: dict[tuple[str, str], DietaryDecision] = {}
        for decision in decisions:
            key = (decision.recipe_id, decision.flag)
            incumbent = self._by_key.get(key)
            if incumbent is None or _preferred(decision, incumbent, calibration):
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
        if decision is None or not _is_current(decision, summary, self._calibration):
            return True
        return decision.probability >= self._calibration.threshold_for(flag)


def _preferred(candidate: DietaryDecision, incumbent: DietaryDecision, calibration: DietaryCalibration) -> bool:
    """Whether `candidate` speaks for the current question better than `incumbent`."""
    if _answers_current_question(candidate, calibration) != _answers_current_question(incumbent, calibration):
        return _answers_current_question(candidate, calibration)
    return (candidate.computed_at, candidate.criteria_hash) > (incumbent.computed_at, incumbent.criteria_hash)


def _answers_current_question(decision: DietaryDecision, calibration: DietaryCalibration) -> bool:
    question = dietary_enrichment_question(decision.flag)
    return (
        question is not None
        and decision.criteria_hash == question.criteria_hash
        and calibration.model.accepts(decision.model)
    )


def _is_current(decision: DietaryDecision, summary: RecipeSummary, calibration: DietaryCalibration) -> bool:
    # Thresholds are calibrated to one model identity (`model` is the endpoint's dated snapshot of it) and to the
    # criteria text; a decision only speaks for the title and ingredients it was asked about.
    # A flag that is no longer asked about (the old nut-free) can't be current, whatever it was computed under.
    question = dietary_enrichment_question(decision.flag)
    return (
        question is not None
        and calibration.model.accepts(decision.model)
        and decision.content_hash == content_fingerprint(summary.title, summary.ingredient_names)
        and decision.criteria_hash == question.criteria_hash
    )
