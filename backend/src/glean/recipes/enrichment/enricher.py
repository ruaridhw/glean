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
model its bar was measured on. Anything else is stale, and the runner asks again.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

from glean.decisions import DEFAULT_MODEL, DecisionModel
from glean.recipes.attributes import UNSURE

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from glean.decisions import Decision, Question
    from glean.recipes.answers import RecipeAnswer
    from glean.recipes.search_index import RecipeSummary
    from glean.recipes.stored import StoredRecipe

__all__ = [
    "DEFAULT_ATTRIBUTE_BAR",
    "MIN_ATTRIBUTE_BAR",
    "Acceptance",
    "AnswerState",
    "ConfidenceBar",
    "Enricher",
    "EnrichmentQuestion",
    "SafeSide",
    "StoredValue",
    "UncalibratedModelError",
    "answer_state",
    "attribute_bar",
    "choice_above_bar",
    "level_above_bar",
    "method_state",
    "question_hash",
    "recipe_state",
]


class UncalibratedModelError(Exception):
    """A client or an answer names a model a question's bar wasn't measured on, so nothing may decide on it."""


# What an acceptance rule stores for one question: the probability that decided the answer, and — for a
# `choice` or `score` question — the value it accepted (a label, a bucket, or `unsure`). A `noul` answer is
# its probability, so its value stays None and pre-V5 dietary lines are unchanged (ADR 0025, spec 6.1).
@dataclass(frozen=True)
class StoredValue:
    """One question's answer, as it will be stored."""

    probability: float
    value: str | None = None


# Given the whole decision, return what to store, or None when the enricher would rather the question stayed
# open than stored an answer. None means "ask again next run", and it is not `unsure`: an attribute below its
# bar still stores a value, because "we asked and are not sure" is an answer that stops the question being
# re-asked and paid for on every run.
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
    model: DecisionModel = DEFAULT_MODEL
    """The model the bar was measured on (#216): its answers are the only ones this question accepts."""

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
            and self.model.accepts(answer.model)
        )

    def served_identity(self, model: str) -> str:
        """The identity an answer may be stored under, refused unless this question's model covers it."""
        if not self.model.accepts(model):
            raise UncalibratedModelError(
                f"The endpoint answered {self.name!r} as {model!r}, which its {self.model.request!r} bar does not cover"
            )
        return model


class Enricher(Protocol):
    """A family of questions asked about every recipe.

    The runner takes a sequence of these, so a new family (V5's attributes) joins the same request without
    the runner changing. An enricher declares questions; it never asks, batches or stores them itself.
    """

    name: str

    def questions(self) -> Sequence[EnrichmentQuestion]:
        """Every question this family asks about each recipe, in the order they should be reported."""
        ...

    def state(self, recipe: StoredRecipe | None) -> Mapping[str, Any]:
        """Extra state this family's questions need, beyond the recipe's title and ingredients.

        The runner merges it into the request only when this family has a question to ask, so a dietary run
        pays for no method text. A family whose questions read only the ingredients returns nothing.
        """
        ...


# The confidence floor G1 settled for an attribute-style answer, and the bar it starts at (spec 6.1). A bar
# may be tuned per attribute on the labelled sample, never below the floor; below whichever bar applies the
# value is stored as `unsure`, which earns no variety credit and no penalty.
MIN_ATTRIBUTE_BAR = 0.7
DEFAULT_ATTRIBUTE_BAR = 0.8


def attribute_bar(threshold: float = DEFAULT_ATTRIBUTE_BAR) -> ConfidenceBar:
    """An attribute-style question's floor, refusing one looser than G1 allows.

    V5's attributes and active time use this; dietary's bars are exclusion thresholds with `SafeSide.LOW`
    and are not subject to the floor (ADR 0011).
    """
    if not MIN_ATTRIBUTE_BAR <= threshold <= 1.0:
        raise ValueError(f"an attribute bar must be between {MIN_ATTRIBUTE_BAR} and 1.0, not {threshold}")
    return ConfidenceBar(threshold=threshold, safe_side=SafeSide.HIGH)


def choice_above_bar(name: str, bar: ConfidenceBar) -> Acceptance:
    """Accept a `choice` question's top option at or above the bar, and store `unsure` below it.

    Below the bar the answer still exists, so it is stored: `unsure` is what stops a recipe being re-asked
    (and re-paid for) on every run, and it is what the spec means by "earns no variety credit and no
    penalty". The stored probability is the top option's, so a later bar can be retuned from what is stored.
    """

    def accept(decision: Decision) -> StoredValue:
        answer = decision.choice(name)
        top = max(answer.probabilities, key=lambda option: answer.probabilities[option])
        probability = answer.probabilities[top]
        return StoredValue(probability=probability, value=top if probability >= bar.threshold else UNSURE)

    return accept


def level_above_bar(name: str, bar: ConfidenceBar, levels: Sequence[str]) -> Acceptance:
    """The same rule for a `score` question, whose answer is the level with the highest probability.

    `levels` is the question's own level order (`criteria[0]` first), so the stored value is the level's
    label rather than its index.
    """

    def accept(decision: Decision) -> StoredValue:
        answer = decision.score(name)
        top = max(answer.probabilities, key=lambda index: answer.probabilities[index])
        probability = answer.probabilities[top]
        return StoredValue(probability=probability, value=levels[top] if probability >= bar.threshold else UNSURE)

    return accept


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


def recipe_state(summary: RecipeSummary) -> dict[str, str | list[str]]:
    """What the decision model is shown about a recipe: its title and its ingredient names."""
    return {"recipe_title": summary.title, "ingredients": list(summary.ingredient_names)}


def method_state(recipe: StoredRecipe | None) -> dict[str, list[str]]:
    """The recipe's method, step by step, for the questions that read it.

    `None` is a recipe the projection lists and the table no longer has; the questions still get asked, with
    no method to read, rather than the run failing on a corpus that is briefly inconsistent.
    """
    return {"method": [] if recipe is None else [step.text for step in recipe.instructions]}
