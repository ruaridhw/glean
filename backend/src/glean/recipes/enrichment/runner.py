"""The enrichment runner: one decision request per recipe, every answer stored on its own.

For each recipe the runner collects every question that is **missing or stale across all enrichers** —
stale when the stored answer replied to other criteria text, to other recipe content, or under another
model — and sends them in **one** `DecisionClient.decide` request. A recipe with nothing to ask makes no
request at all. Then it stores each answer through F1's corpus seam (`save_answers`), so an answer lands
as its own `ANSWER#<question>#<criteria_hash>` item in the `glean-recipes` table or as its line in the
blob corpus, and rebuilds the projection once at the end.

Nothing here knows what a dietary flag or a cuisine is: it takes enrichers, which declare their questions
(`enricher.py`). Adding V5's attributes joins the same per-recipe request without touching this module.

**Resumable without a progress file.** The stored answers are the checkpoint: a run that stops partway has
written the answers it got, so the next run finds them current and asks only what is left. Answers are
written every `checkpoint_every` recipes, and again (with the rebuild) if the run is interrupted.
"""

from __future__ import annotations

import inspect
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from glean.decisions import DecisionError
from glean.observability import logger
from glean.recipes.answers import RecipeAnswer, content_fingerprint
from glean.recipes.enrichment.coverage import AnswerFailure, CoverageReport, QuestionCoverage
from glean.recipes.enrichment.dietary import DIETARY_ENRICHER
from glean.recipes.enrichment.enricher import AnswerState, answer_state, recipe_state

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from glean.decisions import DecisionClient
    from glean.recipes.corpus import RecipeCorpusStore
    from glean.recipes.enrichment.enricher import Enricher, EnrichmentQuestion
    from glean.recipes.search_index import RecipeSummary

__all__ = [
    "CHECKPOINT_EVERY",
    "CorpusUnavailableError",
    "EnrichmentError",
    "run_enrichment",
]

# Recipes between answer writes. Small enough that an interrupted run loses only its last few requests.
CHECKPOINT_EVERY = 25
_EVERYTHING = 1_000_000

type _QuestionKey = tuple[str, str]  # (recipe id, question name)


class CorpusUnavailableError(Exception):
    """The run can't see any corpus recipe, so there is nothing coverage could be measured against."""


class EnrichmentError(Exception):
    """The enrichers can't be run as given (no questions, or two enrichers claiming one question)."""


def run_enrichment(
    corpus: RecipeCorpusStore,
    client: DecisionClient | None,
    *,
    enrichers: Sequence[Enricher] = (DIETARY_ENRICHER,),
    dry_run: bool = False,
    max_workers: int = 8,
    limit: int | None = None,
    checkpoint_every: int = CHECKPOINT_EVERY,
) -> CoverageReport:
    """Ask every recipe what it is missing or stale on, store the answers, and report coverage.

    `dry_run` works out what would be asked and returns without calling the model or writing anything, so
    `client` may be None. `limit` asks about the first N recipes only, for a smoke run.
    """
    questions = _declared_questions(enrichers)
    summaries = sorted(_corpus_summaries(corpus), key=lambda summary: summary.external_id)
    selected = summaries[:limit] if limit is not None else summaries
    known = _answers_by_question(corpus.answers())
    work = [(summary, missing) for summary in selected if (missing := _missing(questions, summary, known))]
    if dry_run:
        return _report(summaries, questions, known, planned=len(work), dry_run=True)
    if client is None:
        raise EnrichmentError("a run needs a decision client unless it is a dry run")

    requests, produced, failures = 0, 0, []
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_ask, client, summary, missing): (summary, missing) for summary, missing in work}
            try:
                for completed, future in enumerate(as_completed(futures), start=1):
                    summary, missing = futures[future]
                    requests += 1
                    try:
                        asked = future.result()
                    except DecisionError as exc:
                        # One recipe the model couldn't answer must not stop the run: it stays uncovered
                        # and the next run asks again.
                        failures.extend(
                            AnswerFailure(summary.external_id, question.name, str(exc)) for question in missing
                        )
                        logger.warning(
                            "enrichment request failed",
                            extra={"recipe_id": summary.external_id, "error": str(exc)},
                        )
                        continue
                    for answer in asked:
                        _remember(known, answer)
                    produced += len(asked)
                    if completed % checkpoint_every == 0:
                        _store_answers(corpus, known)
            except BaseException:
                # An aborted run must stop spending money on questions it will never read the answers to.
                for future in futures:
                    future.cancel()
                raise
    finally:
        # A run that got some answers publishes them even if it died: the stored answers are the checkpoint.
        if produced:
            _store_answers(corpus, known)
            corpus.rebuild_index()

    return _report(summaries, questions, known, requests=requests, stored=produced, failures=failures)


def _ask(client: DecisionClient, summary: RecipeSummary, questions: Sequence[EnrichmentQuestion]) -> list[RecipeAnswer]:
    """One request for every question this recipe is missing or stale on."""
    decision = client.decide(recipe_state(summary), {question.name: question.question for question in questions})
    computed_at = datetime.now(UTC)
    content_hash = content_fingerprint(summary.title, summary.ingredient_names)
    return [
        RecipeAnswer(
            recipe_id=summary.external_id,
            question=question.name,
            probability=value,
            model=decision.model,
            content_hash=content_hash,
            criteria_hash=question.criteria_hash,
            computed_at=computed_at,
        )
        for question in questions
        if (value := question.accept(decision)) is not None
    ]


def _store_answers(corpus: RecipeCorpusStore, known: Mapping[_QuestionKey, Sequence[RecipeAnswer]]) -> None:
    """Write every answer the run holds, through F1's seam.

    Dynamo's `rebuild_projection=False` is F1's bulk path (the one the migration uses): the run ends with
    one authoritative rebuild instead of an S3 write per checkpoint. The blob adapter has no projection, so
    it takes the whole batch — which it needs anyway, since its JSONL is rewritten in full.
    """
    batch = [answer for answers in known.values() for answer in answers]
    save_answers = cast("Callable[..., int]", corpus.store.save_answers)
    if "rebuild_projection" in inspect.signature(save_answers).parameters:
        save_answers(batch, rebuild_projection=False)
    else:
        save_answers(batch)


def _report(
    summaries: Sequence[RecipeSummary],
    questions: Sequence[EnrichmentQuestion],
    known: Mapping[_QuestionKey, Sequence[RecipeAnswer]],
    *,
    requests: int = 0,
    stored: int = 0,
    planned: int = 0,
    dry_run: bool = False,
    failures: Sequence[AnswerFailure] = (),
) -> CoverageReport:
    """Count every recipe against every question, as things now stand."""
    coverage = {question.name: QuestionCoverage(name=question.name, bar=question.bar) for question in questions}
    failed = {(failure.recipe_id, failure.question) for failure in failures}
    incomplete: list[str] = []
    for summary in summaries:
        gap = False
        content_hash = content_fingerprint(summary.title, summary.ingredient_names)
        for question in questions:
            counts = coverage[question.name]
            if (summary.external_id, question.name) in failed:
                counts.failed += 1
                gap = True
                continue
            state = answer_state(
                question, known.get((summary.external_id, question.name), ()), content_hash=content_hash
            )
            if state is AnswerState.CURRENT:
                counts.current += 1
                continue
            gap = True
            if state is AnswerState.STALE:
                counts.stale += 1
            else:
                counts.missing += 1
        if gap:
            incomplete.append(summary.external_id)
    return CoverageReport(
        recipes=len(summaries),
        questions=[coverage[question.name] for question in questions],
        requests=requests,
        answers_stored=stored,
        stated_active_time=sum(1 for summary in summaries if summary.active_time_mins is not None),
        rebuilt=stored > 0,
        dry_run=dry_run,
        planned_requests=planned,
        incomplete=incomplete,
        failures=list(failures),
    )


def _missing(
    questions: Sequence[EnrichmentQuestion],
    summary: RecipeSummary,
    known: Mapping[_QuestionKey, Sequence[RecipeAnswer]],
) -> tuple[EnrichmentQuestion, ...]:
    """The questions this recipe has no current answer to, in enricher order."""
    content_hash = content_fingerprint(summary.title, summary.ingredient_names)
    return tuple(
        question
        for question in questions
        if answer_state(question, known.get((summary.external_id, question.name), ()), content_hash=content_hash)
        is not AnswerState.CURRENT
    )


def _declared_questions(enrichers: Sequence[Enricher]) -> list[EnrichmentQuestion]:
    questions: list[EnrichmentQuestion] = []
    names: set[str] = set()
    for enricher in enrichers:
        for question in enricher.questions():
            if question.name in names:
                raise EnrichmentError(f"{question.name!r} is declared by more than one enricher")
            names.add(question.name)
            questions.append(question)
    if not questions:
        raise EnrichmentError("no enricher declared a question, so there is nothing to ask")
    return questions


def _corpus_summaries(corpus: RecipeCorpusStore) -> list[RecipeSummary]:
    """The recipes Generate can select: the same summaries, from the same index or projection."""
    summaries, _ = corpus.search(per_page=_EVERYTHING)
    if not summaries:
        raise CorpusUnavailableError("The corpus search index is missing or empty; coverage can't be measured")
    return summaries


def _answers_by_question(answers: Sequence[RecipeAnswer]) -> dict[_QuestionKey, list[RecipeAnswer]]:
    """Every stored answer, grouped by (recipe, question). A reworded question keeps all its old answers here."""
    known: dict[_QuestionKey, list[RecipeAnswer]] = {}
    for answer in answers:
        known.setdefault((answer.recipe_id, answer.question), []).append(answer)
    return known


def _remember(known: dict[_QuestionKey, list[RecipeAnswer]], answer: RecipeAnswer) -> None:
    """Hold `answer` beside whatever this recipe already stored for the question, replacing its own key."""
    answers = known.setdefault((answer.recipe_id, answer.question), [])
    for index, stored in enumerate(answers):
        if stored.criteria_hash == answer.criteria_hash:
            answers[index] = answer
            return
    answers.append(answer)
