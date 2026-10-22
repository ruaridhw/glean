"""One stored decision answer, per (recipe, question, criteria hash).

Answers are derived data about a recipe, not part of its body: F1 stores the dietary decisions here
(#125/#159) and F2's enrichers add the attribute and active-time questions to the same shape.

The question name is the stable handle. Dietary questions are named `dietary:<flag>` so a flag keeps
its answers when the question text is reworded (the criteria hash, not the name, says which wording an
answer replied to). A pre-F1 dietary JSONL line carries `flag` and no `question` and reads through here
unchanged; a dumped answer still carries `flag` so the format stays legible either way. (Rolling back to
the blobs does *not* pick up answers computed in dynamo mode — see `AGENTS.md`, "Rolling back to blobs".)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime  # noqa: TC003 - pydantic resolves the field type at runtime
from typing import Any

from pydantic import BaseModel, Field, computed_field, model_validator

DIETARY_QUESTION_PREFIX = "dietary:"

# Not `.json`-suffixed, so `BlobStore.list_keys` never mistakes it for a recipe.
DIETARY_DECISIONS_KEY = "_decisions/dietary.jsonl"


def dietary_question(flag: str) -> str:
    """The stable question name for a dietary flag, e.g. `dietary:tree-nut-free`."""
    return f"{DIETARY_QUESTION_PREFIX}{flag.strip().casefold()}"


def dietary_flag(question: str) -> str | None:
    """The flag a dietary question asks about, or None for a question another enricher owns."""
    if not question.startswith(DIETARY_QUESTION_PREFIX):
        return None
    flag = question.removeprefix(DIETARY_QUESTION_PREFIX).strip()
    return flag or None


def content_fingerprint(title: str, ingredient_names: Any) -> str:
    """Identifies the recipe state an answer assessed, so editing a recipe under its id voids the answer."""
    normalised = [" ".join(name.casefold().split()) for name in ingredient_names]
    payload = json.dumps([" ".join(title.casefold().split()), sorted(normalised)])
    return hashlib.sha256(payload.encode()).hexdigest()


class RecipeAnswer(BaseModel):
    """A decision model's answer about one recipe, with what produced it."""

    recipe_id: str = Field(description="External id of the corpus recipe that was assessed.")
    question: str = Field(description="Stable question name, e.g. `dietary:vegan`.")
    probability: float = Field(ge=0.0, le=1.0, description="Probability the question's `true` holds.")
    model: str = Field(description="Dated snapshot of the decision model that answered.")
    content_hash: str = Field(description="`content_fingerprint` of the recipe state (title, ingredients) assessed.")
    criteria_hash: str = Field(description="Hash of the question's instructions and criteria that were answered.")
    computed_at: datetime = Field(description="When the decision was computed.")

    @model_validator(mode="before")
    @classmethod
    def _from_legacy_flag(cls, data: Any) -> Any:
        if isinstance(data, dict) and not data.get("question") and data.get("flag"):
            return {**data, "question": dietary_question(str(data["flag"]))}
        return data

    @computed_field  # serialised, so a pre-F1 dietary reader still finds the `flag` it knows
    @property
    def flag(self) -> str | None:
        return dietary_flag(self.question)


def latest_per_question(answers: Any) -> list[RecipeAnswer]:
    """One answer per (recipe, question): the most recently computed one.

    A question keeps every answer it has ever had, keyed by criteria hash, so a reworded question leaves the
    previous wording's answer beside the new one. The producer only asks what is missing or stale, so the
    newest answer is the one the current wording produced; keeping both would let an old criteria hash win.
    """
    latest: dict[tuple[str, str], RecipeAnswer] = {}
    for answer in answers:
        key = (answer.recipe_id, answer.question)
        incumbent = latest.get(key)
        if incumbent is None or (answer.computed_at, answer.criteria_hash) > (
            incumbent.computed_at,
            incumbent.criteria_hash,
        ):
            latest[key] = answer
    return sorted(latest.values(), key=lambda answer: (answer.recipe_id, answer.question))
