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
written the answers it got, so the next run finds them current and asks only what is left. What it reads to
find them is the store's own authoritative side — the table's ANSWER items per recipe — never the projection,
which is only published once a run finishes; otherwise a run that died after writing (or whose final rebuild
failed) would pay for the same answers twice. Answers are written every `checkpoint_every` recipes, and again
(with the rebuild) if the run is interrupted.
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
    from collections.abc import Callable, Sequence
    from concurrent.futures import Future

    from glean.decisions import DecisionClient
    from glean.recipes.corpus import CorpusBackend, RecipeCorpusStore
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
    known = _KnownAnswers(corpus.store)
    work = [(summary, missing) for summary in selected if (missing := _missing(questions, summary, known))]
    stated_active_time = _stated_active_time(corpus)
    if dry_run:
        return _report(
            summaries, questions, known, stated_active_time=stated_active_time, planned=len(work), dry_run=True
        )
    if client is None:
        raise EnrichmentError("a run needs a decision client unless it is a dry run")

    run = _Run(corpus, known)
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_ask, client, summary, missing): (summary, missing) for summary, missing in work}
            try:
                for completed, future in enumerate(as_completed(futures), start=1):
                    run.collect(future, *futures[future])
                    if completed % checkpoint_every == 0:
                        run.flush()
            except BaseException:
                # An aborted run must stop spending money on questions it will never read the answers to.
                for future in futures:
                    future.cancel()
                raise
    finally:
        # A run that got some answers publishes them even if it died: the stored answers are the checkpoint.
        if run.produced:
            run.flush()
            corpus.rebuild_index()

    return _report(
        summaries,
        questions,
        known,
        requests=run.requests,
        stored=run.produced,
        stated_active_time=stated_active_time,
        failures=run.failures,
    )


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


class _Run:
    """One run's bookkeeping: what it asked, what came back, what failed, and what it has written."""

    def __init__(self, corpus: RecipeCorpusStore, known: _KnownAnswers) -> None:
        self._corpus = corpus
        self._known = known
        self.requests = 0
        self.produced = 0
        self.failures: list[AnswerFailure] = []

    def collect(
        self, future: Future[list[RecipeAnswer]], summary: RecipeSummary, missing: Sequence[EnrichmentQuestion]
    ) -> None:
        """Take one finished request: store its answers, or record why the recipe is still uncovered."""
        self.requests += 1
        try:
            asked = future.result()
        except DecisionError as exc:
            # One recipe the model couldn't answer must not stop the run: it stays uncovered and the next
            # run asks again.
            self.failures.extend(AnswerFailure(summary.external_id, question.name, str(exc)) for question in missing)
            logger.warning("enrichment request failed", extra={"recipe_id": summary.external_id, "error": str(exc)})
            return
        for answer in asked:
            self._known.remember(answer)
        self.produced += len(asked)

    def flush(self) -> None:
        """Write this checkpoint's answers, so an interrupted run keeps what it paid for."""
        _flush(self._corpus, self._known)


class _KnownAnswers:
    """The answers the store has already persisted, per recipe, plus what this run produced.

    Where the backend can read the answers it holds from its own authoritative side — dynamo queries the
    table's ANSWER items for one recipe — the run asks it, per recipe, and never consults the projection.
    The projection is published when a run finishes, so a run that died after writing answers (or whose
    final rebuild failed) would otherwise re-ask, and re-pay for, work it already has.

    A backend without that read (blobs) keeps every answer in one JSONL, so the run reads that once and
    rewrites it whole; `batch()` is what tells the two apart at write time.
    """

    def __init__(self, store: CorpusBackend) -> None:
        self._read = _per_recipe_reader(store)
        self._answers: dict[str, list[RecipeAnswer]] = {}
        self._pending: dict[tuple[str, str, str], RecipeAnswer] = {}
        if self._read is None:
            for answer in store.answers():
                self._answers.setdefault(answer.recipe_id, []).append(answer)

    def stored(self, recipe_id: str) -> list[RecipeAnswer]:
        """Every answer the store holds for this recipe, published or not."""
        if recipe_id not in self._answers and self._read is not None:
            self._answers[recipe_id] = list(self._read(recipe_id))
        return self._answers.get(recipe_id, [])

    def by_question(self, recipe_id: str) -> dict[str, list[RecipeAnswer]]:
        """The same answers grouped by question name, which is how staleness is asked."""
        grouped: dict[str, list[RecipeAnswer]] = {}
        for answer in self.stored(recipe_id):
            grouped.setdefault(answer.question, []).append(answer)
        return grouped

    def remember(self, answer: RecipeAnswer) -> None:
        """Hold an answer this run produced, to be written at the next checkpoint."""
        question = (answer.question, answer.criteria_hash)
        answers = self._answers.setdefault(answer.recipe_id, [])
        for index, held in enumerate(answers):
            if (held.question, held.criteria_hash) == question:
                answers[index] = answer
                break
        else:
            answers.append(answer)
        self._pending[(answer.recipe_id, *question)] = answer

    def pending(self) -> list[RecipeAnswer]:
        """What this run produced and has not written yet."""
        return list(self._pending.values())

    def batch(self) -> list[RecipeAnswer]:
        """What `save_answers` must be handed: this run's delta, or every answer when the store rewrites all."""
        if self._read is not None:
            return self.pending()
        return [answer for answers in self._answers.values() for answer in answers]

    def flushed(self) -> None:
        self._pending.clear()


def _flush(corpus: RecipeCorpusStore, known: _KnownAnswers) -> None:
    """Write what this checkpoint produced, through F1's seam, and mark it written.

    Dynamo takes the delta with `rebuild_projection=False` (F1's bulk path, the one the migration uses) and
    is rebuilt once at the end: handing it the whole run's answers again would re-put every earlier answer
    at every checkpoint, because the projection it compares against is deliberately not updated until then.
    The blob store has no projection and rewrites its JSONL in full, so it gets everything.
    """
    if not known.pending():
        return
    batch = known.batch()
    save_answers = cast("Callable[..., int]", corpus.store.save_answers)
    if "rebuild_projection" in inspect.signature(save_answers).parameters:
        save_answers(batch, rebuild_projection=False)
    else:
        save_answers(batch)
    known.flushed()


def _report(
    summaries: Sequence[RecipeSummary],
    questions: Sequence[EnrichmentQuestion],
    known: _KnownAnswers,
    *,
    requests: int = 0,
    stored: int = 0,
    stated_active_time: int = 0,
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
                question, known.by_question(summary.external_id).get(question.name, ()), content_hash=content_hash
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
        stated_active_time=stated_active_time,
        rebuilt=stored > 0,
        dry_run=dry_run,
        planned_requests=planned,
        incomplete=incomplete,
        failures=list(failures),
    )


def _missing(
    questions: Sequence[EnrichmentQuestion], summary: RecipeSummary, known: _KnownAnswers
) -> tuple[EnrichmentQuestion, ...]:
    """The questions this recipe has no current answer to, in enricher order."""
    content_hash = content_fingerprint(summary.title, summary.ingredient_names)
    stored = known.by_question(summary.external_id)
    return tuple(
        question
        for question in questions
        if answer_state(question, stored.get(question.name, ()), content_hash=content_hash) is not AnswerState.CURRENT
    )


def _stated_active_time(corpus: RecipeCorpusStore) -> int:
    """How many recipes state an active time (spec 6.1).

    Read from the recipe bodies rather than the projection's summaries: those are only as fresh as the last
    rebuild, and the whole point of the number is that it is true of the corpus, not of a cached index.
    """
    return sum(1 for recipe in corpus.all_recipes() if recipe.active_time_mins is not None)


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


def _per_recipe_reader(store: CorpusBackend) -> Callable[[str], Sequence[RecipeAnswer]] | None:
    """The store's read of the answers it has *persisted* for one recipe, when it can do that.

    Dynamo can: its answers live as items under `RECIPE#<id>`, so one consistent query says what is
    already there whatever the projection says. Blobs cannot — one JSONL holds the whole corpus — so they
    are read once as a batch by `_KnownAnswers` instead. `answers_for` is the seam name this asks for; the
    private one is F1's current name for the same read, which is what runs today.
    """
    for name in ("answers_for", "_answers_for"):
        reader = getattr(store, name, None)
        if callable(reader):
            return cast("Callable[[str], Sequence[RecipeAnswer]]", reader)
    return None
