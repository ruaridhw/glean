"""The active-time enricher: how many hands-on minutes a recipe takes, as one of G1's five buckets.

Q3 found the corpus's stated time is schema.org `prepTime`, not hands-on time: it is there for 35% of
recipes, its median is 10 minutes against a 35-minute median total, and it is really the time before cooking
starts. So active time is estimated for every recipe (spec 6.1, "Enrichers") and the stated value stays where
it is, as `StoredRecipe.prep_time_mins`.

The question is a `score` over the method, with the stated prep and total times in the state as hints. The
answer is bucketed: the bucket the model chose and its probability are stored, and the same bar every
attribute uses (0.8 by default, never below 0.7) decides at read time whether that bucket is trusted. Under
it the answer reads as `unsure`, which makes the household's time cap fall back to total time as it did
before V5.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from glean.decisions import ScoreQuestion
from glean.recipes.attributes import ACTIVE_TIME_QUESTION, ActiveTimeBucket
from glean.recipes.enrichment.enricher import (
    DEFAULT_ATTRIBUTE_BAR,
    EnrichmentQuestion,
    attribute_bar,
    method_state,
    top_level,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from glean.recipes.stored import StoredRecipe

__all__ = ["ACTIVE_TIME_BAR", "ACTIVE_TIME_ENRICHER", "BUCKETS", "ActiveTimeEnricher", "active_time_question"]

# The bucket scale, lowest first, which is the order a `score` question's criteria take.
BUCKETS: tuple[ActiveTimeBucket, ...] = (
    ActiveTimeBucket.UP_TO_15,
    ActiveTimeBucket.FROM_15_TO_30,
    ActiveTimeBucket.FROM_30_TO_45,
    ActiveTimeBucket.FROM_45_TO_60,
    ActiveTimeBucket.OVER_60,
)

_QUESTION = ScoreQuestion(
    instructions=(
        "How many minutes of hands-on work does this recipe take: chopping, stirring, frying, shaping, "
        "checking? Do not count waiting: simmering, roasting, boiling, marinating, resting and chilling are "
        "not hands-on time. Count the work of every stage, including preparation and assembly. The state "
        "gives the source's stated preparation time (prep_time_mins) and its total time (total_time_mins) as "
        "hints: prep_time_mins is often a small fraction of the real hands-on time, so treat it as a lower "
        "bound and not as the answer, and treat total_time_mins as the ceiling."
    ),
    criteria=[
        # Lowest bucket first: a `score` question orders its criteria from the bottom of the scale.
        "Up to 15 minutes of hands-on work: one pan, little chopping, nothing to shape.",
        "15 to 30 minutes of hands-on work: chopping an onion and a few vegetables, one or two pans.",
        "30 to 45 minutes of hands-on work: several stages, browning, a sauce, or shaping.",
        "45 to 60 minutes of hands-on work: multiple stages and pans, or long attention at the hob.",
        "More than an hour of hands-on work: several components, rolling or shaping, or continuous attention.",
    ],
)


# Active time keeps the 0.8 the spec starts at, and it is the one bar the 50-recipe check did not move. The
# model is rarely confident about hands-on work: 35 of the sample's 50 answers were under even the 0.7 floor,
# at 0.70 the 15 it accepted were right 86.7% of the time, and at the shipped 0.80 the sample accepted a single
# answer and that one was wrong (it said 15-30 where the label was "<=15", the safe direction). So the time
# bucket is close to inert in practice: nearly every recipe reads as `unsure` and the household's cap falls
# back to total time, which is what it did before V5. A second sample is what would change this.
ACTIVE_TIME_BAR = DEFAULT_ATTRIBUTE_BAR


@dataclass(frozen=True)
class ActiveTimeEnricher:
    """The active-time question, one per recipe, with the stated times as hints."""

    name: str = "active-time"
    threshold: float = ACTIVE_TIME_BAR

    def questions(self) -> tuple[EnrichmentQuestion, ...]:
        return (active_time_question(self.threshold),)

    def state(self, recipe: StoredRecipe | None) -> Mapping[str, object]:
        """The method, and the times the source already states, as the hints the question reads."""
        return {
            **method_state(recipe),
            "prep_time_mins": None if recipe is None else recipe.prep_time_mins,
            "total_time_mins": None if recipe is None else recipe.total_time_mins,
        }


def active_time_question(threshold: float = ACTIVE_TIME_BAR) -> EnrichmentQuestion:
    """The one question, with its bar and its bucket-accepting rule."""
    bar = attribute_bar(threshold)
    return EnrichmentQuestion(
        name=ACTIVE_TIME_QUESTION,
        question=_QUESTION,
        bar=bar,
        accept=top_level(ACTIVE_TIME_QUESTION, [bucket.value for bucket in BUCKETS]),
    )


ACTIVE_TIME_ENRICHER = ActiveTimeEnricher()
