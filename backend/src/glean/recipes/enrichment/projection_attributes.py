"""How a recipe's stored answers become the attributes a projection entry carries.

Planning reads the projection, never the table, so a recipe's attributes have to be in the entry beside its
answers. They are derived from those answers, not stored twice: the answers are the authority, the entry is
a cache, and a rebuild recomputes it (F1/F2's rebuild path). An answer counts only while it is current — the
question's own wording, the recipe's content and the pinned model — and anything else leaves the attribute
`unsure`, exactly as a recipe that has not been enriched yet reads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from glean.recipes.attributes import ATTRIBUTE_QUESTIONS, RecipeAttributes
from glean.recipes.enrichment.active_time import ACTIVE_TIME_ENRICHER
from glean.recipes.enrichment.attributes import ATTRIBUTE_ENRICHER
from glean.recipes.enrichment.enricher import current_value

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from glean.recipes.answers import RecipeAnswer
    from glean.recipes.enrichment.enricher import EnrichmentQuestion

__all__ = ["V5_QUESTIONS", "attributes_from_answers"]

# Every question V5 records an attribute through, by its stored name.
V5_QUESTIONS: dict[str, EnrichmentQuestion] = {
    question.name: question
    for enricher in (ATTRIBUTE_ENRICHER, ACTIVE_TIME_ENRICHER)
    for question in enricher.questions()
}

# Which attribute of the projection entry a question's value belongs in.
_ATTRIBUTE_OF: dict[str, str] = {name: attribute for attribute, name in ATTRIBUTE_QUESTIONS.items()}


def attributes_from_answers(
    answers: Iterable[RecipeAnswer],
    *,
    content_hash: str,
    questions: Mapping[str, EnrichmentQuestion] | None = None,
) -> RecipeAttributes:
    """One recipe's attributes, from the answers that still speak for its current state.

    `answers` is what the projection entry holds (every wording's answer is kept there); only the current
    wording, under the pinned model, about this content counts. Each current answer is then read **under the
    question's bar as it stands now** (`current_value`), not as it stood when the answer was stored: raising a
    bar reads the labels it rejects as `unsure`, and lowering one recovers a label stored under the old bar,
    with no re-ask. `questions` is only for a caller that is measuring a different declaration — the
    check-sample tool — and defaults to the questions this build ships.
    """
    declared = V5_QUESTIONS if questions is None else questions
    values: dict[str, str] = {}
    for answer in answers:
        question = declared.get(answer.question)
        if question is None:
            continue
        value = current_value(question, answer, content_hash=content_hash)
        if value is not None:
            values[_ATTRIBUTE_OF[answer.question]] = value
    return RecipeAttributes.from_mapping(values)
