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
    """A decision model's answer about one recipe, with what produced it.

    A `noul` question's answer is the probability itself, so `value` stays None and every pre-V5 dietary line
    reads and writes back unchanged. A `choice` or `score` question's answer is a value — a label, an
    active-time bucket, or `unsure` when the top option did not clear the question's bar — and `probability`
    is the probability that decided it (the accepted option's, or the top option's when unsure). Adding the
    value is what ADR 0025 deferred to V5: `unsure` is a stored answer, not "nothing stored".
    """

    recipe_id: str = Field(description="External id of the corpus recipe that was assessed.")
    question: str = Field(description="Stable question name, e.g. `dietary:vegan`.")
    probability: float = Field(
        ge=0.0,
        le=1.0,
        description="The probability that decided this answer: P(`true`) for a `noul`, the accepted option otherwise.",
    )
    value: str | None = Field(
        default=None,
        description="The accepted value for a `choice` or `score` question (a label, a bucket, or `unsure`).",
    )
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

    @model_validator(mode="after")
    def _labelled_questions_carry_a_value(self) -> RecipeAnswer:
        # A dietary answer is its probability, so a missing value is the format. Any other question's answer
        # *is* a value: an answer without one would read as a current answer that says nothing.
        if dietary_flag(self.question) is None and self.value is None:
            raise ValueError(f"{self.question!r} is not a dietary question, so its answer must carry a value")
        return self

    @computed_field  # serialised, so a pre-F1 dietary reader still finds the `flag` it knows
    @property
    def flag(self) -> str | None:
        return dietary_flag(self.question)


def latest_per_question(answers: Any) -> list[RecipeAnswer]:
    """One answer per (recipe, question, criteria hash): the most recently computed for that wording.

    A reworded question leaves the previous wording's answer beside the new one, and only the reader knows
    which wording is current (that lives with the questions, not in the store). Collapsing to one answer per
    question here would throw the current answer away whenever an older wording was computed later or tied on
    the timestamp, so each version is kept and the current-wording choice is left to `DietaryDecisions`
    (and F2's runner).
    """
    latest: dict[tuple[str, str, str], RecipeAnswer] = {}
    for answer in answers:
        key = (answer.recipe_id, answer.question, answer.criteria_hash)
        incumbent = latest.get(key)
        if incumbent is None or answer.computed_at > incumbent.computed_at:
            latest[key] = answer
    return sorted(latest.values(), key=lambda answer: (answer.recipe_id, answer.question, answer.criteria_hash))
