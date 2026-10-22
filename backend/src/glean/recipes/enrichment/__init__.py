"""Recipe enrichment: every question a recipe needs answering, in one request per recipe.

The package is a pipeline of three parts (ADR 0025, spec 6.1):

- **Enrichers** declare questions (`enricher.py`). A question carries the wording handed to the decision
  model, its confidence bar, and the rule that turns a raw answer into a stored value. `dietary.py` is the
  first enricher; V5's attributes join as more.
- **The runner** (`runner.py`) collects each recipe's missing or stale questions across every enricher,
  sends them in one `DecisionClient.decide` request, stores every answer through F1's corpus seam, and
  rebuilds the projection once at the end.
- **The coverage report** (`coverage.py`) says, per question, how many recipes are current, stale, missing
  or failed, and how many recipes state an active time.

Enrichment is a producer: it runs ahead of planning, never inside a request (spec 7). `scripts/
enrich_corpus.py` and `make enrich-corpus` are the entry points.
"""

from __future__ import annotations

from glean.recipes.enrichment.coverage import AnswerFailure, CoverageReport, QuestionCoverage
from glean.recipes.enrichment.dietary import DIETARY_ENRICHER, DietaryEnricher
from glean.recipes.enrichment.enricher import (
    Acceptance,
    AnswerState,
    ConfidenceBar,
    Enricher,
    EnrichmentQuestion,
    SafeSide,
    answer_state,
    is_current_model,
    question_hash,
    recipe_state,
)
from glean.recipes.enrichment.runner import (
    CHECKPOINT_EVERY,
    CorpusUnavailableError,
    EnrichmentError,
    run_enrichment,
)

# Every enricher a run can be pointed at by name (`--enricher`). V5's attribute enrichers join here.
ENRICHERS: dict[str, Enricher] = {DIETARY_ENRICHER.name: DIETARY_ENRICHER}

__all__ = [
    "CHECKPOINT_EVERY",
    "DIETARY_ENRICHER",
    "ENRICHERS",
    "Acceptance",
    "AnswerFailure",
    "AnswerState",
    "ConfidenceBar",
    "CorpusUnavailableError",
    "CoverageReport",
    "DietaryEnricher",
    "Enricher",
    "EnrichmentError",
    "EnrichmentQuestion",
    "QuestionCoverage",
    "SafeSide",
    "answer_state",
    "is_current_model",
    "question_hash",
    "recipe_state",
    "run_enrichment",
]
