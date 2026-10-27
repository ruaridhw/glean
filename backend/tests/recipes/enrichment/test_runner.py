"""The enrichment runner (spec 6.1): one request per recipe, per-answer storage, staleness, coverage.

Seams: `run_enrichment` (the pipeline), the corpus store's answers (what it writes, through F1's seam),
and the `DecisionClient` requests it makes, faked at the HTTP boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from glean.decisions import DECISION_MODEL, DecisionModel
from glean.meal_plan.dietary_decisions import DietaryDecisions, DietaryDecisionStore
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.answers import RecipeAnswer, content_fingerprint, dietary_question
from glean.recipes.corpus import BlobCorpusBackend, RecipeCorpusStore
from glean.recipes.dynamo_corpus import DynamoCorpusBackend, ProjectionPublishError
from glean.recipes.enrichment import (
    DIETARY_ENRICHER,
    CorpusUnavailableError,
    DietaryEnricher,
    EnrichmentError,
    UncalibratedModelError,
    run_enrichment,
)
from glean.recipes.enrichment.dietary import (
    CALIBRATED_DIETARY,
    DIETARY_FLAGS,
    TREE_NUT_FREE,
    DietaryCalibration,
    dietary_enrichment_questions,
)
from glean.recipes.enrichment.enricher import ConfidenceBar, EnrichmentQuestion, SafeSide
from glean.recipes.stored import StoredIngredient, StoredRecipe
from tests.conftest import RECIPES_TABLE_NAME
from tests.recipes.enrichment.fakes import DINNER, SNAPSHOT, CountingBackend, DinnerEnricher, FakeDecisionApi
from tests.recipes.fake_projection import InMemoryProjectionStore

BOTH_ENRICHERS = (DIETARY_ENRICHER, DinnerEnricher())
# A free route's request id and the identity it answers under differ, as observed in a pilot (#216).
CANDIDATE = DecisionModel("baseten/mammoth-1:free", served=("baseten/mammoth-1",))
CANDIDATE_SERVED = "baseten/mammoth-1-20261021"
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
    assert pesto["questions"][DINNER]["type"] == "choice"
    assert {pesto["questions"][name]["type"] for name in DIETARY_QUESTIONS} == {"noul"}


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


def test_answers_to_another_wording_live_beside_the_new_one_in_the_table(recipes_table, projections) -> None:
    """A reworded question is a second ANSWER item, so resume must read both and count the current one."""
    corpus = _dynamo_corpus(projections)
    _seed(corpus)
    other_flags = tuple(flag for flag in DIETARY_FLAGS if flag != "vegan")
    _seed_answers(corpus, ["rec_pesto", "rec_tomato"], flags=("vegan",), stale_criteria=True)
    _seed_answers(corpus, ["rec_pesto", "rec_tomato"], flags=other_flags)
    before = {answer.question for answer in corpus.store.answers_for("rec_pesto") if answer.question == "dietary:vegan"}
    assert before == {"dietary:vegan"}

    asked = FakeDecisionApi()
    report = run_enrichment(corpus, asked.client(), enrichers=(DIETARY_ENRICHER,))

    # Only vegan was stale, so the other five answers per recipe were not re-asked.
    assert {frozenset(request["questions"]) for request in asked.requests} == {frozenset({"dietary:vegan"})}
    vegan = [answer for answer in corpus.store.answers_for("rec_pesto") if answer.question == "dietary:vegan"]
    versions = {answer.criteria_hash for answer in vegan}
    assert len(versions) == 2  # the superseded wording's item is kept beside the new one, by item key design
    assert report.question("dietary:vegan").current == 2


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
    # The client refuses any snapshot but the pinned one, so the stale answer is seeded directly.
    corpus = _blob_corpus(tmp_path)
    _seed_answers(corpus, ["rec_pesto", "rec_tomato"], model="typesafe/jev-1.13-20260917")
    assert {answer.model for answer in corpus.answers()} == {"typesafe/jev-1.13-20260917"}

    dry = run_enrichment(corpus, None, enrichers=(DIETARY_ENRICHER,), dry_run=True)

    assert (dry.question("dietary:vegan").stale, dry.question("dietary:vegan").missing) == (2, 0)

    api = FakeDecisionApi()
    report = run_enrichment(corpus, api.client(), enrichers=(DIETARY_ENRICHER,))

    assert len(api.requests) == 2
    assert (report.answers_stored, report.coverage) == (12, 1.0)
    assert SNAPSHOT in {answer.model for answer in corpus.answers()}


def test_a_run_reports_only_the_enrichers_it_was_given(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    run_enrichment(corpus, FakeDecisionApi().client(), enrichers=(DinnerEnricher(),))

    report = run_enrichment(corpus, FakeDecisionApi().client(), enrichers=(DIETARY_ENRICHER,))

    assert {coverage.name for coverage in report.questions} == DIETARY_QUESTIONS
    assert report.coverage == 1.0


def test_an_answer_under_its_bar_is_stored_as_the_top_option_and_reported_unsure(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    # The fake answers 0.9; a 0.95 bar is above it, so the option it chose is not trusted.
    strict = (DIETARY_ENRICHER, DinnerEnricher(threshold=0.95))

    report = run_enrichment(corpus, FakeDecisionApi().client(), enrichers=strict)

    stored = {(answer.recipe_id, answer.question): answer for answer in corpus.answers()}
    dinner = stored[("rec_pesto", DINNER)]
    assert (dinner.value, dinner.probability) == ("dinner", 0.9)  # what the model said, kept as said
    # The bar is read-time: the report counts it unsure without re-asking or re-paying for it.
    assert (report.question(DINNER).current, report.question(DINNER).unsure) == (2, 2)
    # Dietary stores the probability itself and lets the bar decide at read time, so it is untouched.
    assert stored[("rec_pesto", "dietary:vegetarian")].value is None

    asked_again = FakeDecisionApi()
    report = run_enrichment(corpus, asked_again.client(), enrichers=strict)
    assert asked_again.requests == []  # the answer exists: nothing is re-asked or re-paid for
    assert report.question(DINNER).current == 2


def test_an_acceptance_that_stores_nothing_leaves_the_question_to_be_asked_again(tmp_path) -> None:
    """`None` from an acceptance rule still means "nothing stored", which is not the same as `unsure`."""
    corpus = _blob_corpus(tmp_path)
    bar = ConfidenceBar(threshold=0.8, safe_side=SafeSide.HIGH)
    open_ended = EnrichmentQuestion(
        name=DINNER,
        question=DinnerEnricher().questions()[0].question,
        bar=bar,
        accept=lambda decision: None,
    )

    report = run_enrichment(corpus, FakeDecisionApi().client(), enrichers=(_OneQuestion(open_ended),))

    assert corpus.answers() == []
    assert report.question(DINNER).missing == 2

    asked_again = FakeDecisionApi()
    run_enrichment(corpus, asked_again.client(), enrichers=(_OneQuestion(open_ended),))
    assert len(asked_again.requests) == 2


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


def test_a_failed_request_records_why_the_endpoint_refused_it(tmp_path) -> None:
    # The runner sends recipe text only, so it opts in to a short excerpt of the error body for its report.
    corpus = _blob_corpus(tmp_path)
    api = FakeDecisionApi(fail_when=lambda body: body["state"]["recipe_title"] == "Pesto Pasta")

    report = run_enrichment(corpus, api.client(), enrichers=BOTH_ENRICHERS)

    assert "boom" in report.failures[0].error


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
    _seed_answers(corpus, ["rec_tomato"], flags=("vegan",), stale_criteria=True)

    report = run_enrichment(corpus, None, enrichers=(DIETARY_ENRICHER,), dry_run=True)

    assert _counts(report, "dietary:vegan") == (0, 1, 1, 0)
    assert _counts(report, "dietary:vegetarian") == (0, 0, 2, 0)
    assert (report.covered, report.expected) == (0, 12)
    assert report.incomplete == ["rec_pesto", "rec_tomato"]


def test_the_report_counts_every_recipe_against_every_question(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    _seed_answers(corpus, ["rec_tomato"], flags=("vegan",), stale_criteria=True)
    api = FakeDecisionApi(fail_when=lambda body: body["state"]["recipe_title"] == "Tomato Pasta")

    report = run_enrichment(corpus, api.client(), enrichers=(DIETARY_ENRICHER,))

    assert _counts(report, "dietary:vegan") == (1, 0, 0, 1)
    assert _counts(report, "dietary:peanut-free") == (1, 0, 0, 1)
    assert (report.recipes, len(report.questions), report.requests) == (2, 6, 2)
    assert (report.covered, report.expected, report.coverage) == (6, 12, 0.5)
    assert report.incomplete == ["rec_tomato"]
    assert [failure.question for failure in report.failures] == [dietary_question(flag) for flag in DIETARY_FLAGS]


def test_the_report_states_how_many_recipes_give_a_prep_time(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    corpus.save(_recipe("rec_timed", "Ten Minute Noodles", ["noodles"], prep_time_mins=10))

    report = run_enrichment(corpus, FakeDecisionApi().client(), enrichers=(DIETARY_ENRICHER,))

    assert (report.stated_prep_time, report.recipes) == (1, 3)
    assert "Recipes with a stated prep time: 1/3 (33.3%)" in report.render()


def test_answers_persisted_before_a_failed_publication_are_not_paid_for_again(recipes_table, projections) -> None:
    """The projection is published at the end, so a run must resume from the table, not from it."""
    published = _dynamo_corpus(projections)
    _seed(published)
    recipes_only = projections.read()  # the document a fresh process would load: recipes, no answers
    blocked = RecipeCorpusStore(
        DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=_UnpublishableProjectionStore(recipes_only))
    )
    assert blocked.answers() == []  # nothing was published, so the projection says nothing about answers

    with pytest.raises(ProjectionPublishError):
        run_enrichment(blocked, FakeDecisionApi().client(), enrichers=(DIETARY_ENRICHER,))

    resumed = FakeDecisionApi()
    report = run_enrichment(
        RecipeCorpusStore(DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=InMemoryProjectionStore(recipes_only))),
        resumed.client(),
        enrichers=(DIETARY_ENRICHER,),
    )

    assert resumed.requests == []  # the answers were in the table all along
    assert (report.requests, report.answers_stored, report.coverage) == (0, 0, 1.0)


def test_a_crash_after_a_checkpoint_is_resumed_from_the_table(recipes_table, projections) -> None:
    """The first recipe's answers were flushed to the table; a process that never publishes them loses nothing."""
    published = _dynamo_corpus(projections)
    _seed(published)
    recipes_only = projections.read()
    blocked = RecipeCorpusStore(
        DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=_UnpublishableProjectionStore(recipes_only))
    )
    crashing = FakeDecisionApi(crash_when=lambda body: body["state"]["recipe_title"] == "Tomato Pasta")

    with pytest.raises(ProjectionPublishError):
        run_enrichment(blocked, crashing.client(), enrichers=(DIETARY_ENRICHER,), max_workers=1, checkpoint_every=1)
    assert blocked.answers() == []  # the checkpoint went to the table, and publication never happened

    resumed = FakeDecisionApi()
    report = run_enrichment(
        RecipeCorpusStore(DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=InMemoryProjectionStore(recipes_only))),
        resumed.client(),
        enrichers=(DIETARY_ENRICHER,),
        max_workers=1,
    )

    assert [request["state"]["recipe_title"] for request in resumed.requests] == ["Tomato Pasta"]
    assert report.coverage == 1.0


def test_the_dynamo_run_writes_each_answer_once_across_checkpoints(recipes_table, projections) -> None:
    counting = _CountingAnswersBackend(RECIPES_TABLE_NAME, projection=projections)
    corpus = RecipeCorpusStore(counting)
    _seed(corpus)

    run_enrichment(corpus, FakeDecisionApi().client(), enrichers=(DIETARY_ENRICHER,), checkpoint_every=1)

    # A delta per checkpoint, not the whole run's answers again: six answers per recipe, written once each.
    assert counting.batches == [6, 6]
    assert sum(counting.batches) == len(counting.answers())


def test_the_blob_run_still_rewrites_its_whole_jsonl_at_each_checkpoint(tmp_path) -> None:
    corpus, counting = _counting_blob_corpus(tmp_path)

    run_enrichment(corpus, FakeDecisionApi().client(), enrichers=(DIETARY_ENRICHER,), checkpoint_every=1)

    # One JSONL, so every write carries everything the run holds — the fallback the dynamo path avoids.
    assert counting.batches == [6, 12]


def test_the_stated_prep_time_count_is_read_from_the_recipes_themselves(recipes_table, projections) -> None:
    """The projection's summaries are only as fresh as the last rebuild; this number has to be true anyway."""
    corpus = _dynamo_corpus(projections)
    _seed(corpus)
    corpus.save(_recipe("rec_timed", "Ten Minute Noodles", ["noodles"], prep_time_mins=10))

    report = run_enrichment(corpus, FakeDecisionApi().client(), enrichers=(DIETARY_ENRICHER,))

    assert (report.stated_prep_time, report.recipes) == (1, 3)


def test_a_limit_asks_about_the_first_recipes_only(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    api = FakeDecisionApi()

    report = run_enrichment(corpus, api.client(), enrichers=(DIETARY_ENRICHER,), limit=1)

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
    writes_before = projections.writes

    run_enrichment(corpus, FakeDecisionApi().client(), enrichers=BOTH_ENRICHERS, checkpoint_every=1)

    # F1's bulk save path: one authoritative rebuild at the end, not one projection write per checkpoint.
    assert projections.writes - writes_before == 1


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


@dataclass(frozen=True)
class _OneQuestion:
    """An enricher of exactly one declared question, for testing a single acceptance rule."""

    question: EnrichmentQuestion
    name: str = "test-one"

    def questions(self) -> tuple[EnrichmentQuestion, ...]:
        return (self.question,)

    def state(self, recipe) -> dict:
        return {}


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


class _UnpublishableProjectionStore(InMemoryProjectionStore):
    """A projection object that can be read but never published, like a failed conditional write."""

    def store(self, data: bytes, *, etag: str | None) -> bool:
        raise ProjectionPublishError("the projection could not be published")


class _CountingAnswersBackend(DynamoCorpusBackend):
    """The real dynamo backend, recording how many answers each `save_answers` call was handed."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.batches: list[int] = []

    def save_answers(self, answers, *, rebuild_projection: bool = True) -> int:
        self.batches.append(len(answers))
        return super().save_answers(answers, rebuild_projection=rebuild_projection)


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


def _seed_answers(
    corpus: RecipeCorpusStore,
    recipe_ids: list[str],
    *,
    flags: tuple[str, ...] = DIETARY_FLAGS,
    model: str = SNAPSHOT,
    stale_criteria: bool = False,
) -> None:
    """Store answers for the flags named, stale by criteria text or by model, in one write."""
    summaries = {summary.external_id: summary for summary in corpus.search(per_page=1000)[0]}
    questions = dietary_enrichment_questions()
    corpus.save_answers(
        [
            RecipeAnswer(
                recipe_id=recipe_id,
                question=questions[flag].name,
                probability=0.01,
                model=model,
                content_hash=content_fingerprint(summaries[recipe_id].title, summaries[recipe_id].ingredient_names),
                criteria_hash="0" * 64 if stale_criteria else questions[flag].criteria_hash,
                computed_at=datetime(2026, 10, 20, tzinfo=UTC),
            )
            for recipe_id in recipe_ids
            for flag in flags
        ]
    )


def test_a_client_that_accepts_an_identity_the_calibration_does_not_is_refused_before_any_request_or_write(
    tmp_path,
) -> None:
    corpus = _blob_corpus(tmp_path)
    api = FakeDecisionApi()
    # Same request id as the calibration, but it would also accept a different model's answers.
    widened = DecisionModel(DECISION_MODEL, served=("baseten/mammoth-1",))

    with pytest.raises(UncalibratedModelError):
        run_enrichment(corpus, api.client(model=widened))

    assert api.requests == []
    assert corpus.answers() == []


def test_a_client_asking_a_model_the_calibration_does_not_cover_is_refused_before_any_request_or_write(
    tmp_path,
) -> None:
    corpus = _blob_corpus(tmp_path)
    api = FakeDecisionApi(snapshot=CANDIDATE_SERVED)

    with pytest.raises(UncalibratedModelError):
        run_enrichment(corpus, api.client(model=CANDIDATE), enrichers=BOTH_ENRICHERS)

    assert api.requests == []
    assert corpus.answers() == []


def test_a_substitute_calibration_stores_its_served_identity_for_the_reader_under_it(tmp_path) -> None:
    corpus = _blob_corpus(tmp_path)
    substitute = DietaryCalibration(
        model=CANDIDATE,
        thresholds={},
        default_threshold=0.5,
        evidence="Observed responses on neutral samples only: a reference, not a calibration.",
    )
    api = FakeDecisionApi(snapshot=CANDIDATE_SERVED)

    run_enrichment(corpus, api.client(model=CANDIDATE), enrichers=(DietaryEnricher(calibration=substitute),))

    assert {answer.model for answer in corpus.answers()} == {CANDIDATE_SERVED}
    assert {request["model"] for request in api.requests} == {CANDIDATE.request}
    stored = DietaryDecisionStore(corpus.store).load()
    summaries, _ = corpus.search(per_page=100)
    lentils = next(summary for summary in summaries if "pesto" not in " ".join(summary.ingredient_names))
    assert not DietaryDecisions(stored, calibration=substitute).excludes(lentils, TREE_NUT_FREE)
    # The same answers mean nothing at the production calibration's model, so they exclude everything there.
    assert DietaryDecisions(stored, calibration=CALIBRATED_DIETARY).excludes(lentils, TREE_NUT_FREE)


def test_a_question_stores_an_answer_only_under_an_identity_its_model_covers() -> None:
    question = dietary_enrichment_questions()[TREE_NUT_FREE]

    assert question.served_identity(SNAPSHOT) == SNAPSHOT
    with pytest.raises(UncalibratedModelError):
        question.served_identity(CANDIDATE_SERVED)
