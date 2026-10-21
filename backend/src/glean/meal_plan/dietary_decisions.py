"""dietary decisions: stored beside the corpus, read when candidates are chosen.

Generate never calls the decision model. A producer computes one probability per (recipe, flag), stores
them as decision answers in the corpus store, and candidate selection reads them back. The decision is
the only dietary rule: there are no ingredient word lists behind it.

An answer is stored under the stable question name `dietary:<flag>` (see `recipes.answers`), so it lands
in the DynamoDB ANSWER item or the pre-F1 JSONL line without the two stores needing different shapes.
"""

from __future__ import annotations

import hashlib
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from glean.decisions import DEFAULT_MODEL, DecisionError, DecisionModel, NoulCriteria, NoulQuestion
from glean.observability import logger
from glean.recipes.answers import (
    DIETARY_DECISIONS_KEY,
    RecipeAnswer,
    content_fingerprint,
    dietary_flag,
    dietary_question,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from glean.decisions import DecisionClient
    from glean.recipes.corpus import CorpusBackend, RecipeCorpusStore
    from glean.recipes.search_index import RecipeSummary

__all__ = [
    "DIETARY_DECISIONS_KEY",
    "DIETARY_FLAGS",
    "LEGACY_NUT_FREE",
    "PEANUT_FREE",
    "TREE_NUT_FREE",
    "CALIBRATED_DIETARY",
    "CorpusUnavailableError",
    "CoverageReport",
    "DietaryCalibration",
    "DietaryDecision",
    "DietaryDecisionStore",
    "DietaryDecisions",
    "content_fingerprint",
    "dietary_questions",
    "produce_missing_decisions",
    "question_hash",
    "UncalibratedModelError",
]

_EVERYTHING = 1_000_000
_CHECKPOINT_EVERY = 25

TREE_NUT_FREE = "tree-nut-free"
PEANUT_FREE = "peanut-free"
# Spelled by older app builds, which had one nut flag. It stands for both allergies.
LEGACY_NUT_FREE = "nut-free"
# Flags the decision model is asked about. Others (Keto, Paleo) are left to the meal-plan model.
DIETARY_FLAGS = ("vegetarian", "vegan", "dairy-free", "gluten-free", TREE_NUT_FREE, PEANUT_FREE)

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
    thresholds=MappingProxyType({TREE_NUT_FREE: 0.3, PEANUT_FREE: 0.3}),
    default_threshold=0.5,
    evidence=_CALIBRATION_EVIDENCE,
)
TREE_NUT_FREE_THRESHOLD = CALIBRATED_DIETARY.threshold_for(TREE_NUT_FREE)
PEANUT_FREE_THRESHOLD = CALIBRATED_DIETARY.threshold_for(PEANUT_FREE)
PREFERENCE_THRESHOLD = CALIBRATED_DIETARY.default_threshold
THRESHOLDS = CALIBRATED_DIETARY.thresholds


class CorpusUnavailableError(Exception):
    """Candidate selection can't see any corpus recipe, so there is nothing coverage could be measured against."""


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


def question_hash(question: NoulQuestion) -> str:
    """Identifies the question a decision answered, so rewording a flag's criteria voids its old decisions."""
    return hashlib.sha256(question.model_dump_json().encode()).hexdigest()


class DietaryDecisionStore:
    """Dietary decisions as corpus answers: one per (recipe, flag), through whichever backend is open."""

    def __init__(self, corpus: CorpusBackend) -> None:
        self._corpus = corpus

    def load(self) -> list[DietaryDecision]:
        decisions = (_decision_from_answer(answer) for answer in self._corpus.answers())
        return [decision for decision in decisions if decision is not None]

    def save(self, decisions: list[DietaryDecision]) -> None:
        self._corpus.save_answers([_answer_from_decision(decision) for decision in decisions])


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


def _decision_from_answer(answer: RecipeAnswer) -> DietaryDecision | None:
    """The dietary decision a stored answer carries, or None when another enricher owns the question."""
    flag = dietary_flag(answer.question)
    if flag is None:
        return None
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
    """Stored decisions, looked up by (recipe id, flag), read under one calibration."""

    def __init__(self, decisions: list[DietaryDecision], *, calibration: DietaryCalibration) -> None:
        self._by_key = {(decision.recipe_id, decision.flag): decision for decision in decisions}
        self._calibration = calibration

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


def _is_current(decision: DietaryDecision, summary: RecipeSummary, calibration: DietaryCalibration) -> bool:
    # Thresholds are calibrated to one model identity (`model` is the endpoint's dated snapshot of it) and to the
    # criteria text; a decision only speaks for the title and ingredients it was asked about.
    # A flag that is no longer asked about (the old nut-free) can't be current, whatever it was computed under.
    return (
        decision.flag in _QUESTIONS
        and calibration.model.accepts(decision.model)
        and decision.content_hash == content_fingerprint(summary.title, summary.ingredient_names)
        and decision.criteria_hash == question_hash(_QUESTIONS[decision.flag])
    )


# What each question asks, and the household's ingredient policy, given to the model as criteria.
_QUESTIONS: dict[str, NoulQuestion] = {
    "vegetarian": NoulQuestion(
        instructions=(
            "Does this recipe contain meat, poultry, fish, shellfish or another animal-slaughter product? "
            "Caesar dressing (anchovies), Thai curry paste (shrimp paste), fish and oyster sauce and meat stock "
            "all count, as do Worcestershire sauce (anchovies), lard, suet and gelatine. "
            "Parmesan and pesto do not count. Meat-free, vegan and plant-based substitutes are not meat."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains meat, fish, shellfish, gelatine, anchovy or shrimp paste.",
            false="No ingredient is or contains meat, fish or shellfish. Parmesan and pesto are allowed.",
        ),
    ),
    "vegan": NoulQuestion(
        instructions=(
            "Does this recipe contain any animal product? "
            "Naan bread (usually made with yoghurt or milk), pesto (made with cheese), mayonnaise (eggs), honey "
            "and Worcestershire sauce (anchovies) count. Meat-free, vegan and plant-based substitutes, cocoa butter, "
            "peanut and nut butters are not animal products."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains meat, fish, dairy, eggs or honey.",
            false="No ingredient is or contains an animal product. Coconut milk and plant milks are fine.",
        ),
    ),
    "dairy-free": NoulQuestion(
        instructions=(
            "Does this recipe contain dairy? "
            "Whey, buttermilk, ghee, naan bread (usually made with yoghurt or milk) and pesto (made with cheese) "
            "count. "
            "Dairy-free and plant-based substitutes, oat and coconut cream, cocoa butter, peanut and nut butters "
            "are not dairy."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains milk, cheese, butter, cream, yoghurt, whey or buttermilk.",
            false="No ingredient is or contains dairy. Coconut milk and plant milks are fine.",
        ),
    ),
    "gluten-free": NoulQuestion(
        instructions=(
            "Does this recipe contain gluten? Oats count as gluten unless the recipe says gluten-free oats. "
            "Malt vinegar, soy sauce, couscous, barley and rye count, as do gnocchi, wraps, flour tortillas, "
            "noodles and pasta unless labelled gluten-free, and hoisin, teriyaki and kecap manis (made with soy "
            "sauce). Rice, corn (corn tortillas), gram, chickpea, buckwheat, tapioca, potato, coconut and almond "
            "flours are not gluten."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains wheat, barley, rye, malt or oats that aren't gluten-free.",
            false="No ingredient is or contains gluten. Gluten-free oats, rice and cornflour are fine.",
        ),
    ),
    TREE_NUT_FREE: NoulQuestion(
        instructions=(
            "Does this recipe contain tree nuts or anything made from them? "
            "Almonds, cashews, hazelnuts, walnuts, pecans, pistachios, macadamias, Brazil nuts and pine nuts count, "
            "so pesto counts. Marzipan, frangipane, Nutella and other hazelnut spreads, dukkah, romesco, praline "
            "and almond milk count, as does an unspecified nut or nut butter, which may be a tree nut. "
            "A curry paste, seasoning or sauce is not a tree nut unless the name says it has one: assume none is "
            "hidden inside. Peanuts, peanut butter and satay are not tree nuts. "
            "Coconut, coconut milk, nutmeg and seeds are not nuts, and an ingredient labelled nut-free is not a nut."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains a tree nut or pine nut, or a product made from them.",
            false="No ingredient is or contains a tree nut. Peanuts, coconut and nutmeg are not tree nuts.",
        ),
    ),
    PEANUT_FREE: NoulQuestion(
        instructions=(
            "Does this recipe contain peanuts or anything made from them? "
            "Peanut butter, groundnut oil, satay and satay sauce count, as does an unspecified nut "
            "or nut butter, which may be peanut. Tree nuts such as almonds, cashews, walnuts and pine nuts "
            "are not peanuts. Coconut, coconut milk, nutmeg and seeds are not peanuts, and an ingredient "
            "labelled nut-free or peanut-free is not a peanut."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains peanut or groundnut, or a product made from them.",
            false="No ingredient is or contains peanut. Tree nuts, coconut, coconut milk and nutmeg are not peanuts.",
        ),
    ),
}


def dietary_questions(flags: tuple[str, ...] = DIETARY_FLAGS) -> dict[str, NoulQuestion]:
    return {flag: _QUESTIONS[flag] for flag in flags}


@dataclass
class CoverageReport:
    """What a producer run found and did. Coverage counts (recipe, flag) pairs with a current decision."""

    recipes: int
    flags: int
    covered: int = 0
    computed: int = 0
    failures: int = 0
    uncovered: list[str] = field(default_factory=list)  # recipe ids still missing a decision

    @property
    def expected(self) -> int:
        return self.recipes * self.flags

    @property
    def coverage(self) -> float:
        return self.covered / self.expected if self.expected else 1.0

    def render(self) -> str:
        lines = [
            f"Recipes: {self.recipes}",
            f"Decisions computed this run: {self.computed}",
            f"Coverage: {self.covered}/{self.expected} ({self.coverage:.1%})",
        ]
        if self.uncovered:
            lines.append(f"Recipes without full coverage ({len(self.uncovered)}): {', '.join(self.uncovered)}")
        return "\n".join(lines)


def _contract(model: DecisionModel) -> str:
    return " or ".join(repr(base) for base in (model.request, *model.served))


def produce_missing_decisions(
    corpus: RecipeCorpusStore,
    client: DecisionClient,
    *,
    calibration: DietaryCalibration = CALIBRATED_DIETARY,
    flags: tuple[str, ...] = DIETARY_FLAGS,
    max_workers: int = 8,
) -> CoverageReport:
    """Ask the decision model about each (recipe, flag) lacking a current decision, and store the answers.

    One request per recipe carries all its missing flags. A recipe the model can't answer is
    left uncovered (and so excluded under every flag) and retried on the next run. A client asking a
    model the calibration doesn't cover is refused before any request or write.
    """
    # The whole contract, not just the request id: a client that also accepts another model's answers would
    # store rows the calibrated reader then rejects while still reporting full coverage.
    if client.model != calibration.model:
        raise UncalibratedModelError(
            f"The dietary calibration covers {_contract(calibration.model)}, not {_contract(client.model)}: "
            "measure the new model's cutoffs before it decides anything"
        )
    store = DietaryDecisionStore(corpus.store)
    # The recipes Generate can select: sample_corpus_candidates searches the same index.
    summaries, _ = corpus.search(per_page=_EVERYTHING)
    if not summaries:
        raise CorpusUnavailableError("The corpus search index is missing or empty; coverage can't be measured")
    by_id = {summary.external_id: summary for summary in summaries}
    decisions = {
        (d.recipe_id, d.flag): d
        for d in store.load()
        if d.recipe_id in by_id and _is_current(d, by_id[d.recipe_id], calibration)
    }
    report = CoverageReport(recipes=len(summaries), flags=len(flags))

    work = [
        (summary, missing)
        for summary in summaries
        if (missing := tuple(flag for flag in flags if (summary.external_id, flag) not in decisions))
    ]
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_ask, client, summary, missing, calibration): summary for summary, missing in work}
        for future in as_completed(futures):
            summary = futures[future]
            try:
                answered = future.result()
            except DecisionError as exc:
                report.failures += 1
                logger.warning("dietary decision failed", extra={"recipe_id": summary.external_id, "error": str(exc)})
                continue
            for decision in answered:
                decisions[(decision.recipe_id, decision.flag)] = decision
            report.computed += len(answered)
            done += 1
            if done % _CHECKPOINT_EVERY == 0:
                store.save(list(decisions.values()))
    store.save(list(decisions.values()))

    report.covered = sum(1 for summary in summaries for flag in flags if (summary.external_id, flag) in decisions)
    report.uncovered = sorted(
        summary.external_id
        for summary in summaries
        if any((summary.external_id, flag) not in decisions for flag in flags)
    )
    return report


def _ask(
    client: DecisionClient, summary: RecipeSummary, flags: tuple[str, ...], calibration: DietaryCalibration
) -> list[DietaryDecision]:
    state = {"recipe_title": summary.title, "ingredients": summary.ingredient_names}
    answer = client.decide(state, dietary_questions(flags))
    computed_at = datetime.now(UTC)
    return [
        DietaryDecision(
            recipe_id=summary.external_id,
            flag=flag,
            probability=answer.noul(flag).noul,
            model=calibration.served_identity(answer.model),
            content_hash=content_fingerprint(summary.title, summary.ingredient_names),
            criteria_hash=question_hash(_QUESTIONS[flag]),
            computed_at=computed_at,
        )
        for flag in flags
    ]
