"""What an enricher declares, and when a stored answer stops speaking for a recipe.

An **enricher** is one family of questions asked about every corpus recipe: dietary decisions today, the
attribute and active-time questions later (spec 6.1, "Enrichers"). It declares its questions; it does not
know how they are asked, batched, stored or reported — that is the runner's job (`runner.py`).

Each declared question carries the three things a stored answer depends on:

- the **question** itself, handed to `DecisionClient`. Its hash identifies the wording that was answered.
- its **confidence bar** (spec 6.1, "never a bare 0.5"): the probability level that matters, and which
  side of it the household is safe on. Dietary bars are exclusion thresholds (ADR 0011); an attribute's
  bar is a floor below which the answer is not trusted.
- its **acceptance rule**: how a raw answer becomes the stored value. This is where a question decides
  what its bar means — dietary stores the probability itself and lets the bar decide exclusions when
  planning reads it, so nothing is thrown away.

An answer is **current** when it replied to this question's wording, to this recipe's content, under the
pinned model. Anything else is stale, and the runner asks again.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from glean.decisions import DECISION_MODEL

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from glean.decisions import Decision, Question
    from glean.recipes.answers import RecipeAnswer
    from glean.recipes.search_index import RecipeSummary

__all__ = [
    "Acceptance",
    "AnswerState",
    "ConfidenceBar",
    "Enricher",
    "EnrichmentQuestion",
    "SafeSide",
    "StoredValue",
    "answer_state",
    "is_current_model",
    "question_hash",
    "recipe_state",
]

# The endpoint reports the pinned model either as-is or as a dated snapshot of it (`<pinned>-YYYYMMDD`).
_CURRENT_MODEL = re.compile(rf"{re.escape(DECISION_MODEL)}(-\d{{8}})?")

# What an acceptance rule stores for one question. Today's answer item carries a probability and nothing
# else; V5's attribute enrichers widen this to a value (`unsure`, a cuisine) on the same item.
type StoredValue = float
# Given the whole decision, return the value to store, or None when the answer doesn't clear the bar and
# the enricher would rather the question stayed open than stored a guess.
type Acceptance = Callable[[Decision], StoredValue | None]


class SafeSide(StrEnum):
    """Which side of a question's bar the household is safe on."""

    # A low probability is the safe answer: "probably does not contain the allergen".
    LOW = "low"
    # A high probability is the safe answer: "probably the top option", "probably whole food".
    HIGH = "high"


@dataclass(frozen=True)
class ConfidenceBar:
    """Where a question's answer stops being trusted, and on which side.

    One field pair covers both kinds of bar, so the runner, the coverage report and a reviewer read the
    same fact: dietary questions are safe at `LOW` (a recipe that probably breaks no flag), so 0.3 is an
    exclusion threshold; attribute questions are safe at `HIGH`, so 0.8 is a floor.
    """

    threshold: float
    safe_side: SafeSide


@dataclass(frozen=True)
class EnrichmentQuestion:
    """One question an enricher asks about every recipe, with its bar and its acceptance rule."""

    name: str
    """Stable stored name, e.g. `dietary:vegan`. The answer item is keyed by it (F1's documented scheme)."""
    question: Question
    bar: ConfidenceBar
    accept: Acceptance

    @property
    def criteria_hash(self) -> str:
        """Identifies the wording an answer replied to, so rewording one question re-asks only that one."""
        return question_hash(self.question)

    def is_current(self, answer: RecipeAnswer, *, content_hash: str) -> bool:
        """Whether `answer` speaks for this recipe as it is now, under this question as it is now."""
        return (
            answer.question == self.name
            and answer.criteria_hash == self.criteria_hash
            and answer.content_hash == content_hash
            and is_current_model(answer.model)
        )


class Enricher(Protocol):
    """A family of questions asked about every recipe.

    The runner takes a sequence of these, so a new family (V5's attributes) joins the same request without
    the runner changing. An enricher declares questions; it never asks, batches or stores them itself.
    """

    name: str

    def questions(self) -> Sequence[EnrichmentQuestion]:
        """Every question this family asks about each recipe, in the order they should be reported."""
        ...


class AnswerState(StrEnum):
    """How a recipe stands against one question."""

    CURRENT = "current"
    STALE = "stale"
    MISSING = "missing"


def answer_state(question: EnrichmentQuestion, stored: Sequence[RecipeAnswer], *, content_hash: str) -> AnswerState:
    """Whether a recipe has a current answer to `question`, a stale one, or none at all.

    `stored` is every answer already held for this (recipe, question) pair — in dynamo mode a reworded
    question leaves the old item beside the new one, so one of them being current is what counts.
    """
    if not stored:
        return AnswerState.MISSING
    if any(question.is_current(answer, content_hash=content_hash) for answer in stored):
        return AnswerState.CURRENT
    return AnswerState.STALE


def question_hash(question: Question) -> str:
    """Identifies the question a decision answered, so rewording a question voids its old answers."""
    return hashlib.sha256(question.model_dump_json().encode()).hexdigest()


def is_current_model(model: str) -> bool:
    """Whether `model` is the pinned decision model, or a dated snapshot of it.

    Thresholds are calibrated to one snapshot's probabilities and don't carry over to another version, so
    an answer from any other model is stale.
    """
    return _CURRENT_MODEL.fullmatch(model) is not None


def recipe_state(summary: RecipeSummary) -> dict[str, str | list[str]]:
    """What the decision model is shown about a recipe: its title and its ingredient names."""
    return {"recipe_title": summary.title, "ingredients": list(summary.ingredient_names)}
