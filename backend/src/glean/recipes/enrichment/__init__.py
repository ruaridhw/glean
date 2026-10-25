"""Recipe enrichment: every question a recipe needs answering, in one request per recipe.

The package is a pipeline of three parts (ADR 0025, spec 6.1):

- **Enrichers** declare questions (`enricher.py`). A question carries the wording handed to the decision
  model, its confidence bar, and the rule that turns a raw answer into a stored value. `dietary.py` is the
  first enricher; `attributes.py` and `active_time.py` are V5's.
- **The runner** (`runner.py`) collects each recipe's missing or stale questions across every enricher,
  sends them in one `DecisionClient.decide` request, stores every answer through F1's corpus seam, and
  rebuilds the projection once at the end.
- **The coverage report** (`coverage.py`) says, per question, how many recipes are current, stale, missing
  or failed, and how many recipes state an active time.

Enrichment is a producer: it runs ahead of planning, never inside a request (spec 7). `scripts/
enrich_corpus.py` and `make enrich-corpus` are the entry points.
"""

from __future__ import annotations

from glean.recipes.enrichment.active_time import ACTIVE_TIME_ENRICHER, ActiveTimeEnricher, active_time_question
from glean.recipes.enrichment.attributes import ATTRIBUTE_ENRICHER, AttributeEnricher, attribute_questions
from glean.recipes.enrichment.coverage import AnswerFailure, CoverageReport, QuestionCoverage
from glean.recipes.enrichment.dietary import DIETARY_ENRICHER, DietaryEnricher
from glean.recipes.enrichment.enricher import (
    Acceptance,
    AnswerState,
    ConfidenceBar,
    Enricher,
    EnrichmentQuestion,
    SafeSide,
    StoredValue,
    UncalibratedModelError,
    answer_state,
    attribute_bar,
    current_value,
    method_state,
    question_hash,
    recipe_state,
    top_choice,
    top_level,
)
from glean.recipes.enrichment.runner import (
    CHECKPOINT_EVERY,
    DEFAULT_ENRICHERS,
    CorpusUnavailableError,
    EnrichmentError,
    run_enrichment,
)

# Every enricher a run can be pointed at by name (`--enricher`), in the order a run asks them.
ENRICHERS: dict[str, Enricher] = {
    enricher.name: enricher for enricher in (DIETARY_ENRICHER, ATTRIBUTE_ENRICHER, ACTIVE_TIME_ENRICHER)
}

__all__ = [
    "ACTIVE_TIME_ENRICHER",
    "ATTRIBUTE_ENRICHER",
    "CHECKPOINT_EVERY",
    "DEFAULT_ENRICHERS",
    "DIETARY_ENRICHER",
    "ENRICHERS",
    "Acceptance",
    "ActiveTimeEnricher",
    "AnswerFailure",
    "AnswerState",
    "AttributeEnricher",
    "ConfidenceBar",
    "CorpusUnavailableError",
    "CoverageReport",
    "DietaryEnricher",
    "Enricher",
    "EnrichmentError",
    "EnrichmentQuestion",
    "QuestionCoverage",
    "SafeSide",
    "StoredValue",
    "UncalibratedModelError",
    "active_time_question",
    "answer_state",
    "attribute_bar",
    "attribute_questions",
    "current_value",
    "method_state",
    "question_hash",
    "recipe_state",
    "run_enrichment",
    "top_choice",
    "top_level",
]
