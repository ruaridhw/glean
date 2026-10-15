"""Jev dietary decisions: stored beside the corpus, read when candidates are chosen.

Generate never calls Jev. A producer computes one probability per (recipe, flag),
stores them as one JSONL blob in the corpus store, and candidate selection reads
them. A decision can only add an exclusion to the regex rules, never lift one.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - pydantic resolves the annotation at runtime

from pydantic import BaseModel, Field, ValidationError

from glean.decisions import JEV_MODEL
from glean.recipe_api.blob_store import BlobStore  # noqa: TC001 - runtime annotation

# Not `.json`-suffixed, so `BlobStore.list_keys` never mistakes it for a recipe.
DIETARY_DECISIONS_KEY = "_decisions/dietary.jsonl"

NUT_FREE = "nut-free"
# Flags Jev is asked about. Others (Keto, Paleo) are left to the meal-plan model.
DIETARY_FLAGS = ("vegetarian", "vegan", "dairy-free", "gluten-free", NUT_FREE)

# Exclude when the probability that the recipe breaks the flag reaches the threshold.
NUT_FREE_THRESHOLD = 0.2
PREFERENCE_THRESHOLD = 0.5


class DietaryDecision(BaseModel):
    """Jev's probability that a recipe breaks a dietary flag, with what produced it."""

    recipe_id: str
    flag: str
    probability: float = Field(ge=0.0, le=1.0)
    model: str  # the dated snapshot that answered
    computed_at: datetime


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

    def excludes(self, recipe_id: str, flag: str) -> bool:
        """Whether a stored decision rules the recipe out under `flag` (a normalised flag name).

        Nut-free is an allergy, so a recipe with no current decision is excluded.
        Preference flags without one are left to the regex rules.
        """
        if flag not in DIETARY_FLAGS:
            return False
        decision = self._by_key.get((recipe_id, flag))
        if decision is None or not _is_current(decision):
            return flag == NUT_FREE
        threshold = NUT_FREE_THRESHOLD if flag == NUT_FREE else PREFERENCE_THRESHOLD
        return decision.probability >= threshold


def _is_current(decision: DietaryDecision) -> bool:
    # Thresholds are calibrated to one model version; `model` is Jev's dated snapshot of it.
    return decision.model == JEV_MODEL or decision.model.startswith(f"{JEV_MODEL}-")
