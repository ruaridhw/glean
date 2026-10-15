"""dietary decisions: stored beside the corpus, read when candidates are chosen.

Generate never calls the decision model. A producer computes one probability per (recipe, flag),
stores them as one JSONL blob in the corpus store, and candidate selection reads
them. A decision can only add an exclusion to the regex rules, never lift one.
"""

from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

from glean.decisions import DECISION_MODEL, DecisionError, NoulCriteria, NoulQuestion
from glean.observability import logger
from glean.recipe_api.blob_store import BlobStore  # noqa: TC001 - runtime annotation

if TYPE_CHECKING:
    from collections.abc import Iterable

    from glean.decisions import DecisionClient
    from glean.recipes.corpus import RecipeCorpusStore
    from glean.recipes.search_index import RecipeSummary

_CURRENT_MODEL = re.compile(rf"{re.escape(DECISION_MODEL)}(-\d{{8}})?")  # as DecisionClient accepts it
_EVERYTHING = 1_000_000
_CHECKPOINT_EVERY = 25

# Not `.json`-suffixed, so `BlobStore.list_keys` never mistakes it for a recipe.
DIETARY_DECISIONS_KEY = "_decisions/dietary.jsonl"

NUT_FREE = "nut-free"
# Flags the decision model is asked about. Others (Keto, Paleo) are left to the meal-plan model.
DIETARY_FLAGS = ("vegetarian", "vegan", "dairy-free", "gluten-free", NUT_FREE)

# Exclude when the probability that the recipe breaks the flag reaches the threshold.
# Set from the 55-row labelled sample (tests/fixtures/decisions/dietary_sample.json) answered by
# typesafe/jev-1.14-20261014 on 2026-10-15 (re-derived after the retarget from 1.13):
#   recipes that break a flag:  nut-free >= 0.93, vegetarian >= 0.68, vegan >= 0.84,
#                               dairy-free >= 0.87, gluten-free >= 0.88
#   recipes that don't:         nut-free <= 0.23 (tahini 0.23, hummus wrap 0.16; the rest <= 0.08),
#                               preference flags <= 0.25
# Nut-free is an allergy, so its threshold sits 1.5x above the model's noise floor (0.08) and trades two
# tahini-like false exclusions for a margin of 0.81 to the nearest violator. Preferences sit between
# the clusters: 0.15 above the highest clean recipe, 0.28 below the lowest violator.
NUT_FREE_THRESHOLD = 0.12
PREFERENCE_THRESHOLD = 0.4


class CorpusUnavailableError(Exception):
    """Candidate selection can't see any corpus recipe, so there is nothing coverage could be measured against."""


class DietaryDecision(BaseModel):
    """The model's probability that a recipe breaks a dietary flag, with what produced it."""

    recipe_id: str = Field(description="External id of the corpus recipe that was assessed.")
    flag: str = Field(description="Normalised dietary flag the question was about, e.g. nut-free.")
    probability: float = Field(ge=0.0, le=1.0, description="Probability that the recipe breaks the flag.")
    model: str = Field(description="Dated snapshot of the decision model that answered.")
    content_hash: str = Field(description="`content_fingerprint` of the recipe state (title, ingredients) assessed.")
    computed_at: datetime = Field(description="When the decision was computed.")


def content_fingerprint(title: str, ingredient_names: Iterable[str]) -> str:
    """Identifies the recipe state a decision assessed, so editing a recipe under its id voids the decision."""
    normalised = [" ".join(name.casefold().split()) for name in ingredient_names]
    payload = json.dumps([" ".join(title.casefold().split()), sorted(normalised)])
    return hashlib.sha256(payload.encode()).hexdigest()


class DietaryDecisionStore:
    def __init__(self, store: BlobStore) -> None:
        self._store = store

    def load(self) -> list[DietaryDecision]:
        raw = self._store.read(DIETARY_DECISIONS_KEY)
        if raw is None:
            return []
        decisions = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                decisions.append(DietaryDecision.model_validate_json(line))
            except ValidationError:
                continue
        return decisions

    def save(self, decisions: list[DietaryDecision]) -> None:
        ordered = sorted(decisions, key=lambda decision: (decision.recipe_id, decision.flag))
        self._store.write(DIETARY_DECISIONS_KEY, "".join(decision.model_dump_json() + "\n" for decision in ordered))


class DietaryDecisions:
    """Stored decisions, looked up by (recipe id, flag)."""

    def __init__(self, decisions: list[DietaryDecision]) -> None:
        self._by_key = {(decision.recipe_id, decision.flag): decision for decision in decisions}

    def excludes(self, summary: RecipeSummary, flag: str) -> bool:
        """Whether a stored decision rules the recipe out under `flag` (a normalised flag name).

        Nut-free is an allergy, so a recipe with no decision for its current content is excluded.
        Preference flags without one are left to the regex rules.
        """
        if flag not in DIETARY_FLAGS:
            return False
        decision = self._by_key.get((summary.external_id, flag))
        if decision is None or not _is_current(decision, summary):
            return flag == NUT_FREE
        threshold = NUT_FREE_THRESHOLD if flag == NUT_FREE else PREFERENCE_THRESHOLD
        return decision.probability >= threshold


def _is_current(decision: DietaryDecision, summary: RecipeSummary) -> bool:
    # Thresholds are calibrated to one model version (`model` is the model's dated snapshot of it), and a
    # decision only speaks for the title and ingredients it was asked about.
    return _CURRENT_MODEL.fullmatch(decision.model) is not None and decision.content_hash == content_fingerprint(
        summary.title, summary.ingredient_names
    )


# What each question asks, and the household's ingredient policy, given to the model as criteria.
_QUESTIONS: dict[str, NoulQuestion] = {
    "vegetarian": NoulQuestion(
        instructions=(
            "Does this recipe contain meat, poultry, fish, shellfish or another animal-slaughter product? "
            "Caesar dressing (anchovies), Thai curry paste (shrimp paste), fish and oyster sauce, meat stock "
            "and pesto all count. Parmesan on its own does not count."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains meat, fish, shellfish, gelatine, anchovy or shrimp paste.",
            false="No ingredient is or contains meat, fish or shellfish. Parmesan is allowed.",
        ),
    ),
    "vegan": NoulQuestion(
        instructions=(
            "Does this recipe contain any animal product? "
            "Naan bread (usually made with yoghurt or milk) and pesto (made with cheese) count."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains meat, fish, dairy, eggs or honey.",
            false="No ingredient is or contains an animal product. Coconut milk and plant milks are fine.",
        ),
    ),
    "dairy-free": NoulQuestion(
        instructions=(
            "Does this recipe contain dairy? "
            "Whey, buttermilk, ghee, naan bread (usually made with yoghurt or milk) and pesto (made with cheese) count."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains milk, cheese, butter, cream, yoghurt, whey or buttermilk.",
            false="No ingredient is or contains dairy. Coconut milk and plant milks are fine.",
        ),
    ),
    "gluten-free": NoulQuestion(
        instructions=(
            "Does this recipe contain gluten? Oats count as gluten unless the recipe says gluten-free oats. "
            "Malt vinegar, soy sauce, couscous, barley and rye count."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains wheat, barley, rye, malt or oats that aren't gluten-free.",
            false="No ingredient is or contains gluten. Gluten-free oats, rice and cornflour are fine.",
        ),
    ),
    NUT_FREE: NoulQuestion(
        instructions=(
            "Does this recipe contain nuts, peanuts or anything made from them? "
            "Pine nuts count as nuts, so pesto counts. Marzipan, frangipane, Nutella and other hazelnut "
            "spreads, dukkah, romesco and almond milk count. Coconut, coconut milk, nutmeg and seeds are not nuts."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains a tree nut, peanut or pine nut, or a product made from them.",
            false="No ingredient is or contains a nut or peanut. Coconut, coconut milk and nutmeg are not nuts.",
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


def produce_missing_decisions(
    corpus: RecipeCorpusStore,
    client: DecisionClient,
    *,
    flags: tuple[str, ...] = DIETARY_FLAGS,
    max_workers: int = 8,
) -> CoverageReport:
    """Ask the decision model about each (recipe, flag) lacking a current decision, and store the answers.

    One request per recipe carries all its missing flags. A recipe the model can't answer is
    left uncovered (and so excluded under nut-free) and retried on the next run.
    """
    store = DietaryDecisionStore(corpus.store)
    # The recipes Generate can select: sample_corpus_candidates searches the same index.
    summaries, _ = corpus.search(per_page=_EVERYTHING)
    if not summaries:
        raise CorpusUnavailableError("The corpus search index is missing or empty; coverage can't be measured")
    by_id = {summary.external_id: summary for summary in summaries}
    decisions = {
        (d.recipe_id, d.flag): d for d in store.load() if d.recipe_id in by_id and _is_current(d, by_id[d.recipe_id])
    }
    report = CoverageReport(recipes=len(summaries), flags=len(flags))

    work = [
        (summary, missing)
        for summary in summaries
        if (missing := tuple(flag for flag in flags if (summary.external_id, flag) not in decisions))
    ]
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_ask, client, summary, missing): summary for summary, missing in work}
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


def _ask(client: DecisionClient, summary: RecipeSummary, flags: tuple[str, ...]) -> list[DietaryDecision]:
    state = {"recipe_title": summary.title, "ingredients": summary.ingredient_names}
    answer = client.decide(state, dietary_questions(flags))
    computed_at = datetime.now(UTC)
    return [
        DietaryDecision(
            recipe_id=summary.external_id,
            flag=flag,
            probability=answer.noul(flag).noul,
            model=answer.model,
            content_hash=content_fingerprint(summary.title, summary.ingredient_names),
            computed_at=computed_at,
        )
        for flag in flags
    ]
