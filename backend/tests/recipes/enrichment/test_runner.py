"""The enrichment runner (spec 6.1): one request per recipe, per-answer storage, staleness, coverage.

Seams: `run_enrichment` (the pipeline), the corpus store's answers (what it writes, through F1's seam),
and the `DecisionClient` requests it makes, faked at the HTTP boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from glean.decisions import DECISION_MODEL
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.answers import RecipeAnswer, content_fingerprint, dietary_question
from glean.recipes.corpus import BlobCorpusBackend, RecipeCorpusStore
from glean.recipes.dynamo_corpus import DynamoCorpusBackend
from glean.recipes.enrichment import (
    DIETARY_ENRICHER,
    CorpusUnavailableError,
    EnrichmentError,
    run_enrichment,
)
from glean.recipes.enrichment.dietary import DIETARY_FLAGS, dietary_enrichment_questions
from glean.recipes.stored import StoredIngredient, StoredRecipe
from tests.conftest import RECIPES_TABLE_NAME
from tests.recipes.enrichment.fakes import DINNER, SNAPSHOT, CountingBackend, DinnerEnricher, FakeDecisionApi
from tests.recipes.fake_projection import InMemoryProjectionStore

BOTH_ENRICHERS = (DIETARY_ENRICHER, DinnerEnricher())
DIETARY_QUESTIONS = {dietary_question(flag) for flag in DIETARY_FLAGS}


@pytest.fixture
def projections() -> InMemoryProjectionStore:
    """The projection the dynamo backend keeps in step, in memory so no test reaches S3."""
    return InMemoryProjectionStore()


def test_one_request_per_recipe_carries_every_question_missing_from_both_enrichers(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    api = FakeDecisionApi()

    run_enrichment(corpus, api.client(), enrichers=BOTH_ENRICHERS)

    assert len(api.requests) == 2  # two recipes, one request each — not one per question
    pesto = api.asked("Pesto Pasta")
    assert pesto["model"] == DECISION_MODEL
    assert pesto["state"] == {"recipe_title": "Pesto Pasta", "ingredients": ["spaghetti", "basil pesto"]}
    assert set(pesto["questions"]) == {*DIETARY_QUESTIONS, DINNER}
    assert {question["type"] for question in pesto["questions"].values()} == {"noul"}


def test_every_answer_is_stored_on_its_own_with_what_produced_it(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)

    report = run_enrichment(corpus, FakeDecisionApi().client(), enrichers=BOTH_ENRICHERS)

    stored = {(answer.recipe_id, answer.question): answer for answer in corpus.answers()}
    assert set(stored) == {
        (recipe_id, question) for recipe_id in ("rec_pesto", "rec_tomato") for question in {*DIETARY_QUESTIONS, DINNER}
    }
    pesto = stored[("rec_pesto", "dietary:tree-nut-free")]
    assert pesto.probability == 0.9  # the fake reads pesto as tree nut, peanut and animal product alike
    assert stored[("rec_tomato", "dietary:tree-nut-free")].probability == 0.01
    assert pesto.model == SNAPSHOT
    assert pesto.criteria_hash == dietary_enrichment_questions()["tree-nut-free"].criteria_hash
    assert (report.requests, report.answers_stored, report.coverage) == (2, 14, 1.0)


def test_a_recipe_with_nothing_missing_makes_no_request(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    run_enrichment(corpus, FakeDecisionApi().client(), enrichers=BOTH_ENRICHERS)
    second = FakeDecisionApi()

    report = run_enrichment(corpus, second.client(), enrichers=BOTH_ENRICHERS)

    assert second.requests == []
    assert (report.requests, report.answers_stored, report.coverage) == (0, 0, 1.0)


def test_a_reworded_question_re_asks_only_that_question(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    run_enrichment(corpus, FakeDecisionApi().client(), enrichers=BOTH_ENRICHERS)
    reworded = FakeDecisionApi()

    report = run_enrichment(
        corpus,
        reworded.client(),
        enrichers=(DIETARY_ENRICHER, DinnerEnricher(instructions="Is this served in the evening?")),
    )

    assert len(reworded.requests) == 2
    assert {frozenset(request["questions"]) for request in reworded.requests} == {frozenset({DINNER})}
    assert report.question(DINNER).current == 2


def test_a_changed_recipe_re_asks_all_of_its_questions(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    run_enrichment(corpus, FakeDecisionApi().client(), enrichers=BOTH_ENRICHERS)
    _save(corpus, "rec_tomato", "Tomato Pasta", ["spaghetti", "tomato", "basil pesto"])
    changed = FakeDecisionApi()

    report = run_enrichment(corpus, changed.client(), enrichers=BOTH_ENRICHERS)

    assert [request["state"]["recipe_title"] for request in changed.requests] == ["Tomato Pasta"]
    assert set(changed.requests[0]["questions"]) == {*DIETARY_QUESTIONS, DINNER}
    assert (report.answers_stored, report.coverage) == (7, 1.0)


def test_an_answer_from_another_model_is_asked_again(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    run_enrichment(corpus, FakeDecisionApi(snapshot="typesafe/jev-1.13-20260917").client())
    api = FakeDecisionApi()

    report = run_enrichment(corpus, api.client())

    assert len(api.requests) == 2
    assert (report.answers_stored, report.coverage) == (12, 1.0)
    assert {answer.model for answer in corpus.answers() if answer.model} == {SNAPSHOT}


def test_a_run_reports_only_the_enrichers_it_was_given(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    run_enrichment(corpus, FakeDecisionApi().client(), enrichers=(DinnerEnricher(),))

    report = run_enrichment(corpus, FakeDecisionApi().client())

    assert {coverage.name for coverage in report.questions} == DIETARY_QUESTIONS
    assert report.coverage == 1.0


def test_an_answer_below_the_bar_is_not_stored_and_is_asked_again(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    # The fake answers 0.9; a 0.95 bar is above it, so nothing clears it.
    strict = (DIETARY_ENRICHER, DinnerEnricher(threshold=0.95))

    run_enrichment(corpus, FakeDecisionApi().client(), enrichers=strict)

    stored = {(answer.recipe_id, answer.question) for answer in corpus.answers()}
    assert ("rec_pesto", DINNER) not in stored  # 0.9 is under the enricher's 0.95 bar
    # Dietary stores the probability itself and lets the bar decide at read time, so it is untouched.
    assert ("rec_pesto", "dietary:vegetarian") in stored

    asked_again = FakeDecisionApi()
    report = run_enrichment(corpus, asked_again.client(), enrichers=strict)
    assert {frozenset(request["questions"]) for request in asked_again.requests} == {frozenset({DINNER})}
    assert report.question(DINNER).missing == 2


def test_a_recipe_the_model_cannot_answer_is_recorded_and_the_run_continues(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    api = FakeDecisionApi(fail_when=lambda body: body["state"]["recipe_title"] == "Pesto Pasta")

    report = run_enrichment(corpus, api.client(), enrichers=BOTH_ENRICHERS)

    assert {answer.recipe_id for answer in corpus.answers()} == {"rec_tomato"}
    assert report.incomplete == ["rec_pesto"]
    assert (report.question("dietary:vegan").failed, report.question("dietary:vegan").current) == (1, 1)
    assert (report.requests, report.failures[0].recipe_id) == (2, "rec_pesto")
    assert report.coverage == 0.5
    assert "Pesto Pasta" not in report.render()  # the report names the recipe, never its content
    assert "rec_pesto" in report.render()


def test_an_interrupted_run_resumes_where_it_stopped(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    crashing = FakeDecisionApi(crash_when=lambda body: body["state"]["recipe_title"] == "Tomato Pasta")

    with pytest.raises(RuntimeError):
        run_enrichment(corpus, crashing.client(), enrichers=BOTH_ENRICHERS, max_workers=1)

    # The run published what it had before it died, so the next run can see it and skip it.
    assert {answer.recipe_id for answer in corpus.answers()} == {"rec_pesto"}

    resumed = FakeDecisionApi()
    report = run_enrichment(corpus, resumed.client(), enrichers=BOTH_ENRICHERS, max_workers=1)

    assert [request["state"]["recipe_title"] for request in resumed.requests] == ["Tomato Pasta"]
    assert report.coverage == 1.0


def test_the_run_rebuilds_the_index_once_at_the_end(tmp_path) -> None:
    corpus, counting = _counting_blob_corpus(tmp_path)

    run_enrichment(corpus, FakeDecisionApi().client(), enrichers=BOTH_ENRICHERS, checkpoint_every=1)

    assert counting.rebuilds == 1
    run_enrichment(corpus, FakeDecisionApi().client(), enrichers=BOTH_ENRICHERS, checkpoint_every=1)
    assert counting.rebuilds == 1  # nothing was written, so there was nothing to rebuild


def test_a_dry_run_reports_what_would_be_asked_and_touches_nothing(tmp_path) -> None:
    corpus, counting = _counting_blob_corpus(tmp_path)

    report = run_enrichment(corpus, None, enrichers=BOTH_ENRICHERS, dry_run=True)

    assert (report.dry_run, report.planned_requests, report.requests, report.answers_stored) == (True, 2, 0, 0)
    assert (counting.answer_writes, counting.rebuilds) == (0, 0)
    assert corpus.answers() == []
    assert "Dry run: 2 recipes would be asked" in report.render()


def test_a_dry_run_counts_what_is_current_stale_and_missing_without_asking(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    _store_stale_answers(corpus, "rec_tomato", flags=("vegan",))

    report = run_enrichment(corpus, None, dry_run=True)

    assert _counts(report, "dietary:vegan") == (0, 1, 1, 0)
    assert _counts(report, "dietary:vegetarian") == (0, 0, 2, 0)
    assert (report.covered, report.expected) == (0, 12)
    assert report.incomplete == ["rec_pesto", "rec_tomato"]


def test_the_report_counts_every_recipe_against_every_question(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    _store_stale_answers(corpus, "rec_tomato", flags=("vegan",))
    api = FakeDecisionApi(fail_when=lambda body: body["state"]["recipe_title"] == "Tomato Pasta")

    report = run_enrichment(corpus, api.client())

    assert _counts(report, "dietary:vegan") == (1, 0, 0, 1)
    assert _counts(report, "dietary:peanut-free") == (1, 0, 0, 1)
    assert (report.recipes, len(report.questions), report.requests) == (2, 6, 2)
    assert (report.covered, report.expected, report.coverage) == (6, 12, 0.5)
    assert report.incomplete == ["rec_tomato"]
    assert [failure.question for failure in report.failures] == [dietary_question(flag) for flag in DIETARY_FLAGS]


def test_the_report_states_how_many_recipes_give_an_active_time(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    corpus.save(_recipe("rec_timed", "Ten Minute Noodles", ["noodles"], active_time_mins=10))

    report = run_enrichment(corpus, FakeDecisionApi().client())

    assert (report.stated_active_time, report.recipes) == (1, 3)
    assert "Recipes with a stated active time: 1/3 (33.3%)" in report.render()


def test_a_limit_asks_about_the_first_recipes_only(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    api = FakeDecisionApi()

    report = run_enrichment(corpus, api.client(), limit=1)

    assert [request["state"]["recipe_title"] for request in api.requests] == ["Pesto Pasta"]
    # The report still describes the whole corpus, so it says who is left.
    assert (report.recipes, report.covered, report.incomplete) == (2, 6, ["rec_tomato"])


def test_the_same_run_reaches_full_coverage_through_the_dynamo_store(recipes_table, projections) -> None:
    corpus = _dynamo_corpus(projections)
    _seed(corpus)
    api = FakeDecisionApi()

    report = run_enrichment(corpus, api.client(), enrichers=BOTH_ENRICHERS)

    assert (report.requests, report.coverage) == (2, 1.0)
    assert len(corpus.answers()) == 14
    second = FakeDecisionApi()
    assert run_enrichment(corpus, second.client(), enrichers=BOTH_ENRICHERS).requests == 0
    assert second.requests == []


def test_the_dynamo_run_writes_the_projection_once_not_once_per_checkpoint(recipes_table, projections) -> None:
    corpus = _dynamo_corpus(projections)
    _seed(corpus)
    projections.writes = 0

    run_enrichment(corpus, FakeDecisionApi().client(), enrichers=BOTH_ENRICHERS, checkpoint_every=1)

    assert projections.writes == 1  # F1's bulk save path: one authoritative rebuild at the end


def test_two_enrichers_declaring_one_question_is_refused(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)

    with pytest.raises(EnrichmentError, match="more than one enricher"):
        run_enrichment(corpus, FakeDecisionApi().client(), enrichers=(DinnerEnricher(), DinnerEnricher()))


def test_a_run_with_no_questions_is_refused(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)

    with pytest.raises(EnrichmentError, match="nothing to ask"):
        run_enrichment(corpus, FakeDecisionApi().client(), enrichers=())


def test_a_corpus_with_no_visible_recipes_fails_loudly(tmp_path) -> None:
    api = FakeDecisionApi()

    with pytest.raises(CorpusUnavailableError):
        run_enrichment(RecipeCorpusStore(BlobCorpusBackend(_blobs(tmp_path))), api.client())

    assert api.requests == []


def test_a_run_that_is_not_a_dry_run_needs_a_client(tmp_path) -> None:
    with pytest.raises(EnrichmentError, match="decision client"):
        run_enrichment(_blob_corpus(tmp_path), None)


def _counts(report, question: str) -> tuple[int, ...]:
    coverage = report.question(question)
    return (coverage.current, coverage.stale, coverage.missing, coverage.failed)


def _blobs(tmp_path) -> FilesystemBlobStore:
    return FilesystemBlobStore(tmp_path)


def _blob_corpus(tmp_path) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(BlobCorpusBackend(_blobs(tmp_path)))
    _seed(corpus)
    return corpus


def _counting_blob_corpus(tmp_path) -> tuple[RecipeCorpusStore, CountingBackend]:
    counting = CountingBackend(_blobs(tmp_path))
    corpus = RecipeCorpusStore(counting)
    _seed(corpus)
    counting.rebuilds = 0  # a fresh corpus builds its index as the seeds land; count what the run does
    return corpus, counting


def _dynamo_corpus(projections) -> RecipeCorpusStore:
    return RecipeCorpusStore(DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=projections))


def _seed(corpus: RecipeCorpusStore) -> None:
    _save(corpus, "rec_pesto", "Pesto Pasta", ["spaghetti", "basil pesto"])
    _save(corpus, "rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])


def _save(corpus: RecipeCorpusStore, external_id: str, title: str, ingredients: list[str], **extra) -> None:
    corpus.save(_recipe(external_id, title, ingredients, **extra))


def _recipe(external_id: str, title: str, ingredients: list[str], **extra) -> StoredRecipe:
    return StoredRecipe(
        external_id=external_id,
        title=title,
        ingredients=[StoredIngredient(canonical_name=name, quantity=1, unit="each") for name in ingredients],
        **extra,
    )


def _store_stale_answers(corpus: RecipeCorpusStore, recipe_id: str, *, flags: tuple[str, ...]) -> None:
    """Answers that replied to other criteria text, for the flags named."""
    summary = next(summary for summary in corpus.search(per_page=1000)[0] if summary.external_id == recipe_id)
    questions = dietary_enrichment_questions()
    corpus.save_answers(
        [
            RecipeAnswer(
                recipe_id=recipe_id,
                question=questions[flag].name,
                probability=0.01,
                model=SNAPSHOT,
                content_hash=content_fingerprint(summary.title, summary.ingredient_names),
                criteria_hash="0" * 64,
                computed_at=datetime(2026, 10, 20, tzinfo=UTC),
            )
            for flag in flags
        ]
    )
