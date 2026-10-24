"""The DynamoDB corpus backend against moto, using the table exactly as template.yaml defines it."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from botocore.exceptions import ClientError

from glean.decisions import DECISION_MODEL
from glean.meal_plan.candidates import sample_corpus_candidates
from glean.meal_plan.dietary_decisions import (
    DietaryDecision,
    DietaryDecisions,
    DietaryDecisionStore,
    content_fingerprint,
    dietary_questions,
    question_hash,
)
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes import dynamo_corpus
from glean.recipes.answers import RecipeAnswer, dietary_question
from glean.recipes.corpus import RecipeCorpusStore, recipe_blob_key
from glean.recipes.dynamo_corpus import (
    DynamoCorpusBackend,
    ProjectionPublishError,
    RecipeTooLargeError,
    answer_item,
    answer_sk,
    recipe_pk,
    retry_throttled,
    source_pk,
)
from glean.recipes.projection import PROJECTION_TTL_SECONDS, loads
from glean.recipes.search_index import RecipeSummary
from glean.recipes.stored import StoredInstruction
from tests.conftest import RECIPES_TABLE_NAME
from tests.recipes.corpus_fixtures import synthetic_corpus, synthetic_recipe
from tests.recipes.fake_projection import InMemoryProjectionStore

if TYPE_CHECKING:
    from pathlib import Path

    from glean.recipes.projection import RecipeProjection

COMPUTED_AT = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
CURRENT_MODEL = f"{DECISION_MODEL}-20261014"
TREE_NUT_FREE = "tree-nut-free"


class _AlwaysConflictingStore:
    """A publisher that always loses the version race."""

    def __init__(self, inner: InMemoryProjectionStore) -> None:
        self.inner = inner
        self.reads = 0

    def read(self) -> bytes | None:
        return self.inner.read()

    def load(self) -> Any:
        self.reads += 1
        return self.inner.load()

    def store(self, data: bytes, *, etag: str | None) -> bool:
        return False


class _RefusingStore:
    """A permanent refusal on the first publish; the object never moved."""

    def __init__(self, inner: InMemoryProjectionStore) -> None:
        self.inner = inner
        self.failures = 1

    def read(self) -> bytes | None:
        return self.inner.read()

    def load(self) -> Any:
        return self.inner.load()

    def store(self, data: bytes, *, etag: str | None) -> bool:
        if self.failures:
            self.failures -= 1
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")
        return self.inner.store(data, etag=etag)


class _SlowDownOnceStore:
    """S3's SlowDown on the first publish: the same object, worth retrying."""

    def __init__(self, inner: InMemoryProjectionStore) -> None:
        self.inner = inner
        self.failures = 1

    def read(self) -> bytes | None:
        return self.inner.read()

    def load(self) -> Any:
        return self.inner.load()

    def store(self, data: bytes, *, etag: str | None) -> bool:
        if self.failures:
            self.failures -= 1
            raise ClientError({"Error": {"Code": "SlowDown"}}, "PutObject")
        return self.inner.store(data, etag=etag)


class _CountingProjectionStore(InMemoryProjectionStore):
    def __init__(self) -> None:
        super().__init__()
        self.reads = 0

    def read(self) -> bytes | None:
        self.reads += 1
        return super().read()


@pytest.fixture
def projections() -> _CountingProjectionStore:
    return _CountingProjectionStore()


@pytest.fixture
def backend(recipes_table: Any, projections: _CountingProjectionStore) -> DynamoCorpusBackend:
    return DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=projections)


def test_a_saved_recipe_round_trips_through_the_table(backend: DynamoCorpusBackend) -> None:
    recipe = synthetic_corpus()[0]

    backend.save(recipe)

    assert backend.get(recipe.external_id) == recipe
    assert backend.get("rec_missing") is None


def test_an_import_url_resolves_through_its_source_pointer(backend: DynamoCorpusBackend, recipes_table: Any) -> None:
    recipe = synthetic_recipe(
        "rec_tomato_pasta",
        title="Tomato Pasta",
        ingredients=["spaghetti", "tomato"],
        source_url="https://example.com/tomato-pasta?utm=campaign",
    )

    backend.save(recipe)

    assert backend.get_by_source_url("https://example.com/tomato-pasta?utm=campaign") == recipe
    assert backend.get_by_source_url("https://example.com/elsewhere") is None
    pointer = recipes_table.get_item(Key={"pk": source_pk(recipe.source_url), "sk": "RECIPE"})["Item"]
    assert pointer["recipe_id"] == recipe.external_id


def test_the_recipe_and_its_source_pointer_are_one_item_each(backend: DynamoCorpusBackend, recipes_table: Any) -> None:
    recipe = synthetic_recipe(
        "rec_tomato_pasta", title="Tomato Pasta", ingredients=["tomato"], source_url="https://example.com/p"
    )

    backend.save(recipe)

    rows = recipes_table.scan()["Items"]
    assert sorted(row["sk"] for row in rows) == ["RECIPE", "RECIPE"]
    assert {row["pk"] for row in rows} == {recipe_pk(recipe.external_id), source_pk(recipe.source_url)}


def test_a_recipe_imported_without_a_url_gets_no_source_pointer(
    backend: DynamoCorpusBackend, recipes_table: Any
) -> None:
    backend.save(synthetic_recipe("rec_one", title="One", ingredients=["rice"]))
    backend.save(synthetic_recipe("rec_two", title="Two", ingredients=["peas"]))

    assert [row["pk"] for row in recipes_table.scan()["Items"] if row["pk"].startswith("SOURCE#")] == []
    assert backend.get_by_source_url("") is None
    assert backend.get("rec_one") is not None
    assert backend.get("rec_two") is not None


def test_saving_an_unchanged_recipe_writes_nothing_the_second_time(backend: DynamoCorpusBackend) -> None:
    recipe = synthetic_corpus()[0]

    assert backend.upsert(recipe) is True
    assert backend.upsert(recipe) is False


def test_a_recipe_over_the_size_budget_is_refused_with_a_clear_error(backend: DynamoCorpusBackend) -> None:
    oversized = synthetic_recipe("rec_big", title="Big", ingredients=["rice"]).model_copy(
        update={"instructions": [StoredInstruction(step_number=1, phase="main", text="x" * 12_000)]}
    )

    with pytest.raises(RecipeTooLargeError, match="over the corpus's 10000 byte budget"):
        backend.save(oversized)

    assert backend.get("rec_big") is None


def test_search_returns_exactly_what_the_blob_corpus_returns(tmp_path: Path, backend: DynamoCorpusBackend) -> None:
    blobs = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    dynamo = RecipeCorpusStore(backend)
    for recipe in synthetic_corpus():
        blobs.save(recipe)
        dynamo.save(recipe)

    for criteria in (
        {},
        {"q": "tomato"},
        {"q": "cur"},
        {"q": "curry"},
        {"q": "zzz"},
        {"cuisine": "italian"},
        {"dietary": "vegan"},
        {"dietary": "vegan, gluten-free"},
        {"q": "tacos", "cuisine": "mexican"},
        {"per_page": 1, "page": 2},
    ):
        assert blobs.search(**criteria) == dynamo.search(**criteria), criteria


def test_a_summary_from_the_projection_carries_the_blob_key_that_recipe_would_have(
    backend: DynamoCorpusBackend,
) -> None:
    recipe = synthetic_recipe("rec_plain", title="Plain Rice", ingredients=["rice"])

    backend.index()  # no projection yet
    backend.save(recipe)

    summaries, total = RecipeCorpusStore(backend).search(q="rice")

    assert total == 1
    assert summaries[0].key == recipe_blob_key("rec_plain")


def test_answers_for_reads_only_that_recipes_answers_in_dynamo_mode(backend: DynamoCorpusBackend) -> None:
    for recipe in synthetic_corpus():
        backend.save(recipe)
    answers = [
        _answer("rec_tomato_pasta", "vegan", 0.02),
        _answer("rec_tomato_pasta", "peanut-free", 0.02),
        _answer("rec_bean_tacos", "vegan", 0.02),
    ]
    backend.save_answers(answers)

    assert backend.answers_for("rec_tomato_pasta") == sorted(
        answers[:2], key=lambda answer: (answer.question, answer.criteria_hash)
    )
    assert backend.answers_for("rec_missing") == []
    assert RecipeCorpusStore(backend).answers_for("rec_bean_tacos") == [answers[2]]


class _PagingQueryClient:
    """A DynamoDB client whose Query returns two pages, like a recipe with many historical answers."""

    def __init__(self) -> None:
        self.pages = [
            {"Items": [{"recipe_id": "rec_a", "_page": 1}], "LastEvaluatedKey": {"pk": "a", "sk": "1"}},
            {"Items": [{"recipe_id": "rec_a", "_page": 2}]},
        ]
        self.calls: list[dict[str, Any]] = []

    def query(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.pages[len(self.calls) - 1]


def test_answers_for_reads_every_page_of_a_paged_query(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = DynamoCorpusBackend.__new__(DynamoCorpusBackend)
    client = _PagingQueryClient()
    backend._client, backend._table = client, "glean-recipes-test"
    rows: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "glean.recipes.dynamo_corpus._answer_from_row", lambda row: rows.append(row) or _row_answer(row)
    )

    answers = backend.answers_for("rec_a")

    assert len(client.calls) == 2
    assert client.calls[1]["ExclusiveStartKey"] == {"pk": "a", "sk": "1"}
    assert all(call["ConsistentRead"] is True for call in client.calls)
    assert all(call["KeyConditionExpression"] == "pk = :pk AND begins_with(sk, :answers)" for call in client.calls)
    assert [answer.question for answer in answers] == ["dietary:page-1", "dietary:page-2"]
    assert [row["_page"] for row in rows] == [1, 2]


def _row_answer(row: dict[str, Any]) -> RecipeAnswer:
    return RecipeAnswer(
        recipe_id="rec_a",
        question=f"dietary:page-{row['_page']}",
        probability=0.02,
        model=CURRENT_MODEL,
        content_hash="c" * 64,
        criteria_hash=f"{row['_page']:064x}",
        computed_at=COMPUTED_AT,
    )


def test_answers_for_returns_every_answer_of_a_recipe_that_spans_several_pages(
    recipes_table: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """The reviewer's 3,001-answer case: the current answer sits on the page a single Query never reads."""
    recipe = next(r for r in synthetic_corpus() if r.external_id == "rec_tomato_pasta")
    object_store = InMemoryProjectionStore()
    backend = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=object_store)
    backend.save(recipe)
    fingerprint = content_fingerprint(recipe.title, [i.canonical_name for i in recipe.ingredients])
    current = _answer(recipe.external_id, "vegan", 0.02).model_copy(
        update={"content_hash": fingerprint, "criteria_hash": "f" * 64}
    )
    historical = [
        current.model_copy(update={"criteria_hash": f"{number:064x}", "probability": 0.9}) for number in range(3_000)
    ]
    for start in range(0, len(historical), 500):
        backend._client.batch_write_item(
            RequestItems={
                RECIPES_TABLE_NAME: [
                    {"PutRequest": {"Item": answer_item(answer)}} for answer in historical[start : start + 500]
                ]
            }
        )
    backend._client.put_item(TableName=RECIPES_TABLE_NAME, Item=answer_item(current))
    first_page = backend._client.query(
        TableName=RECIPES_TABLE_NAME,
        KeyConditionExpression="pk = :pk AND begins_with(sk, :answers)",
        ExpressionAttributeValues={":pk": recipe_pk(recipe.external_id), ":answers": "ANSWER#"},
        ConsistentRead=True,
    )
    assert "LastEvaluatedKey" in first_page
    assert len(first_page["Items"]) < 3_001

    answers = backend.answers_for(recipe.external_id)

    assert len(answers) == 3_001
    assert current in answers
    # A publication right after a full rebuild must not truncate the recipe's answers back to one page.
    backend.rebuild_projection()
    backend.save(recipe)
    projected = backend.projection().by_id(recipe.external_id)
    assert projected is not None
    assert len(projected.answers) == 3_001
    assert current in projected.answers


def test_answers_for_falls_back_to_the_table_even_when_the_projection_is_stale(
    backend: DynamoCorpusBackend,
) -> None:
    recipe = synthetic_corpus()[0]
    backend.save(recipe)
    backend.save_answers([_answer(recipe.external_id, "vegan", 0.02)])
    backend.projection()  # warm this process's read cache before the write another process would make

    # A second process writes an answer; the first one's cache never sees it.
    other = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=backend._projections)
    other.save_answers([_answer(recipe.external_id, "peanut-free", 0.02)])
    backend.projection()

    assert [answer.question for answer in backend.answers_for(recipe.external_id)] == [
        "dietary:peanut-free",
        "dietary:vegan",
    ]


def test_an_answer_lands_in_the_table_and_in_the_projection(
    backend: DynamoCorpusBackend, recipes_table: Any, projections: _CountingProjectionStore
) -> None:
    recipe = synthetic_corpus()[0]
    backend.save(recipe)
    answer = _answer(recipe.external_id, "vegan", 0.02)

    assert backend.save_answers([answer]) == 1
    assert backend.answers() == [answer]

    row = recipes_table.get_item(
        Key={"pk": recipe_pk(recipe.external_id), "sk": answer_sk("dietary:vegan", answer.criteria_hash)}
    )["Item"]
    assert (row["question"], float(row["probability"]), row["content_hash"]) == (
        "dietary:vegan",
        0.02,
        answer.content_hash,
    )
    assert _projection(projections).by_id(recipe.external_id).answers == [answer]
    assert backend.save_answers([answer]) == 0


@pytest.mark.parametrize("stale_is_newer", [True, False])
@pytest.mark.parametrize("stale_hash", ["f" * 64, "0" * 64])
def test_the_store_and_a_rebuild_keep_the_current_wording_even_when_the_stale_answer_is_newer(
    recipes_table: Any, stale_is_newer: bool, stale_hash: str
) -> None:
    recipe = next(r for r in synthetic_corpus() if r.external_id == "rec_tomato_pasta")
    projections = InMemoryProjectionStore()
    backend = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=projections)
    backend.save(recipe)
    current = _answer("rec_tomato_pasta", "vegan", 0.02)
    stale = current.model_copy(
        update={
            "criteria_hash": stale_hash,
            "probability": 0.9,
            "computed_at": current.computed_at if stale_is_newer else datetime(2026, 9, 1, tzinfo=UTC),
        }
    )
    if stale_is_newer:
        current = current.model_copy(update={"computed_at": datetime(2026, 9, 1, tzinfo=UTC)})

    backend.save_answers([stale, current])
    backend.rebuild_projection()

    for projection in (backend.projection(), loads(projections.data)):
        answered = projection.by_id("rec_tomato_pasta")
        assert answered is not None
        assert {answer.criteria_hash for answer in answered.answers} == {stale_hash, current.criteria_hash}
    assert (
        DietaryDecisions(DietaryDecisionStore(backend).load()).excludes(
            RecipeSummary.from_recipe(recipe, key="k"), "vegan"
        )
        is False
    )


def test_an_answer_for_superseded_recipe_content_is_kept_out_of_the_projection(
    backend: DynamoCorpusBackend, projections: _CountingProjectionStore
) -> None:
    recipe = synthetic_corpus()[0]
    backend.save(recipe)
    stale = _answer(recipe.external_id, "vegan", 0.02).model_copy(update={"content_hash": "0" * 64})

    backend.save_answers([stale])

    assert _projection(projections).by_id(recipe.external_id).answers == []


def test_rebuilding_the_projection_from_the_table_restores_a_lost_one(
    backend: DynamoCorpusBackend, projections: _CountingProjectionStore
) -> None:
    for recipe in synthetic_corpus():
        backend.save(recipe)
    backend.save_answers([_answer("rec_tomato_pasta", "vegan", 0.02)])
    lost = _projection(projections)

    cold = _CountingProjectionStore()  # a Lambda that never saw the projection
    rebuilt = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=cold).rebuild_projection()

    assert rebuilt.recipes == 3
    assert rebuilt.written is True
    assert loads(cold.data) == lost
    assert DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=cold).rebuild_projection().written is False


def test_the_projection_is_read_once_within_its_five_minute_ttl(
    backend: DynamoCorpusBackend, projections: _CountingProjectionStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [1_000.0]
    monkeypatch.setattr(dynamo_corpus.time, "monotonic", lambda: clock[0])
    backend.save(synthetic_corpus()[0])
    reads = projections.reads

    for _ in range(3):
        RecipeCorpusStore(backend).search(q="tomato")

    assert projections.reads == reads

    clock[0] += PROJECTION_TTL_SECONDS + 1

    assert RecipeCorpusStore(backend).search(q="tomato")[1] == 1
    assert projections.reads == reads + 1


def test_planning_applies_the_same_dietary_decisions_in_both_modes(
    tmp_path: Path, backend: DynamoCorpusBackend
) -> None:
    blobs = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    dynamo = RecipeCorpusStore(backend)

    offered = {}
    for corpus in (blobs, dynamo):
        _seed(corpus)
        offered[corpus] = _offered(corpus)

    assert offered[blobs] == offered[dynamo] == {"rec_tomato_pasta"}


# -- concurrent writers must not lose each other's projection entries ----------------------------
# The projection is one S3 object published by every writer, so a writer that publishes its own cached
# snapshot silently drops entries another process saved. These tests use two views of one object, which
# reproduces it without threads.


def test_two_writers_do_not_lose_each_others_projection_entries(recipes_table: Any) -> None:
    published = InMemoryProjectionStore()
    first = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=published.view())
    second = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=published.view())
    first.index()  # both writers warm their own 5-minute cache on the empty document
    second.index()
    recipes = synthetic_corpus()

    first.save(recipes[0])
    second.save(recipes[1])
    first.save(recipes[2])

    assert sorted(recipe.summary.external_id for recipe in _projection(published).recipes) == [
        "rec_bean_tacos",
        "rec_chicken_curry",
        "rec_tomato_pasta",
    ]
    assert RecipeCorpusStore(second).search(q="tomato")[1] == 1


def test_a_writer_that_saved_nothing_else_still_publishes_over_the_fresh_document(recipes_table: Any) -> None:
    published = InMemoryProjectionStore()
    stale = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=published.view())
    other = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=published.view())
    recipes = synthetic_corpus()
    stale.index()
    other.save(recipes[0])

    stale.save(recipes[1])

    assert {recipe.summary.external_id for recipe in _projection(published).recipes} == {
        recipes[0].external_id,
        recipes[1].external_id,
    }


def test_answers_from_two_writers_are_all_kept(recipes_table: Any) -> None:
    published = InMemoryProjectionStore()
    first = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=published.view())
    second = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=published.view())
    for recipe in synthetic_corpus():
        first.save(recipe)
    first.index()
    second.index()

    first.save_answers([_answer("rec_tomato_pasta", "vegan", 0.02)])
    second.save_answers([_answer("rec_bean_tacos", "vegan", 0.02)])

    assert {(answer.recipe_id, answer.question) for answer in _projection(published).answers()} == {
        ("rec_tomato_pasta", "dietary:vegan"),
        ("rec_bean_tacos", "dietary:vegan"),
    }


def test_a_transient_publish_error_is_retried_within_the_bound(recipes_table: Any) -> None:
    object_store = InMemoryProjectionStore()
    backend = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=_SlowDownOnceStore(object_store))

    assert backend.upsert(synthetic_corpus()[0]) is True
    assert [recipe.summary.external_id for recipe in _projection(object_store).recipes] == ["rec_tomato_pasta"]


class _SlowReadOnceStore:
    """S3's SlowDown on the first GET of the projection, then healthy: a blip, not a failure."""

    def __init__(self, inner: InMemoryProjectionStore) -> None:
        self.inner = inner
        self.reads = 0

    def read(self) -> bytes | None:
        return self.inner.read()

    def load(self) -> Any:
        self.reads += 1
        if self.reads == 1:
            raise ClientError({"Error": {"Code": "SlowDown"}}, "GetObject")
        return self.inner.load()

    def store(self, data: bytes, *, etag: str | None) -> bool:
        return self.inner.store(data, etag=etag)


class _BrokenReadStore:
    """Every GET of the projection fails transiently."""

    def __init__(self) -> None:
        self.reads = 0

    def read(self) -> bytes | None:
        return None

    def load(self) -> Any:
        self.reads += 1
        raise ClientError({"Error": {"Code": "InternalError"}}, "GetObject")

    def store(self, data: bytes, *, etag: str | None) -> bool:
        return True


def test_a_transient_projection_read_is_retried_within_the_bound(recipes_table: Any) -> None:
    published = _SlowReadOnceStore(InMemoryProjectionStore())
    backend = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=published)
    recipe = synthetic_corpus()[0]

    assert backend.upsert(recipe) is True

    assert published.reads >= 2
    assert [entry.summary.external_id for entry in _projection(published.inner).recipes] == [recipe.external_id]


def test_a_projection_read_that_never_recovers_is_reported_with_the_repair_command(
    recipes_table: Any, caplog: pytest.LogCaptureFixture
) -> None:
    published = _BrokenReadStore()
    backend = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=published)
    recipe = synthetic_corpus()[0]

    with pytest.raises(ProjectionPublishError, match="build_recipe_index"):
        backend.save(recipe)

    assert published.reads == 4  # the same bounded attempts as a failed write
    assert backend.get(recipe.external_id) == recipe
    assert any("planning will not see it" in record.getMessage() for record in caplog.records)


def test_a_transient_read_before_saving_answers_is_retried_too(recipes_table: Any) -> None:
    object_store = InMemoryProjectionStore()
    backend = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=_SlowReadOnceStore(object_store))
    recipe = synthetic_corpus()[0]
    backend.save(recipe)

    assert backend.save_answers([_answer(recipe.external_id, "vegan", 0.02)]) == 1


def test_a_publish_that_keeps_losing_the_race_is_reported_with_the_repair_command(
    recipes_table: Any, caplog: pytest.LogCaptureFixture
) -> None:
    published = _AlwaysConflictingStore(InMemoryProjectionStore())
    backend = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=published)
    recipe = synthetic_corpus()[0]

    with pytest.raises(ProjectionPublishError, match="build_recipe_index"):
        backend.save(recipe)

    assert any(recipe.external_id in record.getMessage() for record in caplog.records)
    assert backend.get(recipe.external_id) == recipe


def test_a_retry_after_a_failed_publish_repairs_the_projection_without_rewriting_the_recipe(
    recipes_table: Any,
) -> None:
    object_store = InMemoryProjectionStore()
    published = _RefusingStore(object_store)
    backend = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=published)
    recipe = synthetic_corpus()[0]

    with pytest.raises(ProjectionPublishError):
        backend.save(recipe)

    published.failures = 0
    retried = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=object_store.view())

    assert retried.upsert(recipe) is True  # nothing new to store: only the projection was missing
    assert [entry.summary.external_id for entry in _projection(object_store).recipes] == [recipe.external_id]


# -- a full publication must re-read the table, not republish a snapshot -------------------------


class _InterleavingStore:
    """A projection object that lets another writer run before the first conditional publish."""

    def __init__(self, inner: InMemoryProjectionStore, *, before_first_store: Any) -> None:
        self.inner = inner
        self.before_first_store = before_first_store
        self.stores = 0

    def read(self) -> bytes | None:
        return self.inner.read()

    def load(self) -> Any:
        return self.inner.load()

    def store(self, data: bytes, *, etag: str | None) -> bool:
        self.stores += 1
        if self.stores == 1 and self.before_first_store is not None:
            self.before_first_store()
        return self.inner.store(data, etag=etag)


def test_a_full_rebuild_rescans_the_table_after_losing_the_race(recipes_table: Any) -> None:
    """The reviewer's reproduction: a rebuild's precomputed document must not overwrite a concurrent save."""
    first, second = synthetic_corpus()[:2]
    DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=InMemoryProjectionStore()).save(first)

    raced = InMemoryProjectionStore()  # the projection is missing: the documented rebuild case

    def other_writer_saves_second() -> None:
        DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=raced.view()).save(second)

    interleaved = _InterleavingStore(raced.view(), before_first_store=other_writer_saves_second)
    rebuilt = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=interleaved).rebuild_projection()

    assert interleaved.stores == 2
    assert rebuilt.recipes == 2
    assert sorted(recipe.summary.external_id for recipe in _projection(raced).recipes) == sorted(
        [first.external_id, second.external_id]
    )


class _VanishingStore:
    """The projection object is deleted by someone else between a writer's read and its write."""

    def __init__(self, inner: InMemoryProjectionStore) -> None:
        self.inner = inner
        self.vanished = False

    def read(self) -> bytes | None:
        return self.inner.read()

    def load(self) -> Any:
        return self.inner.load()

    def store(self, data: bytes, *, etag: str | None) -> bool:
        if etag is not None and not self.vanished:
            self.vanished = True
            self.inner.delete()
            return False
        return self.inner.store(data, etag=etag)


def test_a_publish_survives_the_projection_object_being_deleted_between_read_and_write(
    recipes_table: Any,
) -> None:
    racing = _VanishingStore(InMemoryProjectionStore())
    backend = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=racing)
    first, second = synthetic_corpus()[:2]

    backend.save(first)
    backend.save(second)

    # The object was deleted by a third party, so the recreated document holds what this writer knows about;
    # the point is that the publish retried and succeeded rather than failing on NoSuchKey.
    assert racing.vanished is True
    assert [recipe.summary.external_id for recipe in _projection(racing.inner).recipes] == [second.external_id]


def test_a_rebuild_that_keeps_losing_the_race_gives_up_with_the_repair_command(
    recipes_table: Any, caplog: pytest.LogCaptureFixture
) -> None:
    first = synthetic_corpus()[0]
    DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=InMemoryProjectionStore()).save(first)
    backend = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=_AlwaysConflictingStore(InMemoryProjectionStore()))

    with pytest.raises(ProjectionPublishError, match="build_recipe_index"):
        backend.rebuild_projection()

    assert any("full rebuild" in record.getMessage() for record in caplog.records)


# -- retry policy --------------------------------------------------------------------------------


def _throttled() -> ClientError:
    return ClientError({"Error": {"Code": "ProvisionedThroughputExceededException"}}, "TransactWriteItems")


def test_a_throttled_write_is_retried_with_exponential_backoff() -> None:
    sleeps: list[float] = []
    calls: list[int] = []

    def operation() -> str:
        calls.append(1)
        if len(calls) <= 2:
            raise _throttled()
        return "written"

    assert retry_throttled(operation, sleep=sleeps.append) == "written"
    assert len(calls) == 3
    assert len(sleeps) == 2
    assert sleeps[1] > sleeps[0]


def test_a_throttle_that_never_recovers_raises_after_the_last_attempt() -> None:
    calls: list[int] = []

    def operation() -> None:
        calls.append(1)
        raise _throttled()

    with pytest.raises(ClientError):
        retry_throttled(operation, attempts=3, sleep=lambda _: None)

    assert len(calls) == 3


def _cancelled(*reasons: str) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": "TransactionCanceledException", "Message": "Transaction cancelled"},
            "CancellationReasons": [
                {"Code": reason, "Message": reason, "Item": {"Key": {"pk": {"S": "RECIPE#x"}}}} for reason in reasons
            ],
        },
        "TransactWriteItems",
    )


def test_a_transaction_cancelled_for_throughput_is_retried() -> None:
    sleeps: list[float] = []
    calls: list[int] = []

    def operation() -> str:
        calls.append(1)
        if len(calls) == 1:
            raise _cancelled("ProvisionedThroughputExceeded")
        return "written"

    assert retry_throttled(operation, sleep=sleeps.append) == "written"
    assert len(calls) == 2
    assert len(sleeps) == 1


def test_a_transaction_conflict_is_retried() -> None:
    calls: list[int] = []

    def operation() -> str:
        calls.append(1)
        if len(calls) == 1:
            raise _cancelled("TransactionConflict")
        return "written"

    assert retry_throttled(operation, sleep=lambda _: None) == "written"
    assert len(calls) == 2


def test_a_transaction_cancelled_by_a_failed_condition_is_not_retried() -> None:
    calls: list[int] = []

    def operation() -> None:
        calls.append(1)
        raise _cancelled("ConditionalCheckFailed", "None")

    with pytest.raises(ClientError):
        retry_throttled(operation, sleep=lambda _: None)

    assert len(calls) == 1


def test_a_mixed_cancellation_is_not_retried() -> None:
    calls: list[int] = []

    def operation() -> None:
        calls.append(1)
        raise _cancelled("ProvisionedThroughputExceeded", "ConditionalCheckFailed")

    with pytest.raises(ClientError):
        retry_throttled(operation, sleep=lambda _: None)

    assert len(calls) == 1


def test_a_real_error_is_not_retried() -> None:
    calls: list[int] = []

    def operation() -> None:
        calls.append(1)
        raise ClientError({"Error": {"Code": "ValidationException"}}, "PutItem")

    with pytest.raises(ClientError):
        retry_throttled(operation, sleep=lambda _: None)

    assert len(calls) == 1


# -- helpers -------------------------------------------------------------------------------------


def _projection(projections: _CountingProjectionStore) -> RecipeProjection:
    assert projections.data is not None
    return loads(projections.data)


def _answer(recipe_id: str, flag: str, probability: float) -> RecipeAnswer:
    recipe = next(r for r in synthetic_corpus() if r.external_id == recipe_id)
    return RecipeAnswer(
        recipe_id=recipe_id,
        question=dietary_question(flag),
        probability=probability,
        model=CURRENT_MODEL,
        content_hash=content_fingerprint(recipe.title, [i.canonical_name for i in recipe.ingredients]),
        criteria_hash=question_hash(dietary_questions()[flag]),
        computed_at=COMPUTED_AT,
    )


def _seed(corpus: RecipeCorpusStore) -> None:
    """Two recipes that both look harmless, one of which a stored decision excludes."""
    corpus.save(synthetic_recipe("rec_pesto", title="Pesto Pasta", ingredients=["spaghetti", "basil pesto"]))
    corpus.save(synthetic_recipe("rec_tomato_pasta", title="Tomato Pasta", ingredients=["spaghetti", "tomato"]))
    DietaryDecisionStore(corpus.store).save(
        [
            DietaryDecision(
                recipe_id=recipe_id,
                flag=flag,
                probability=probability,
                model=CURRENT_MODEL,
                content_hash=content_fingerprint(title, ingredients),
                criteria_hash=question_hash(dietary_questions()[flag]),
                computed_at=COMPUTED_AT,
            )
            for recipe_id, title, ingredients, probability in (
                ("rec_pesto", "Pesto Pasta", ["spaghetti", "basil pesto"], 0.9),
                ("rec_tomato_pasta", "Tomato Pasta", ["spaghetti", "tomato"], 0.02),
            )
            for flag in (TREE_NUT_FREE,)
        ]
    )


def _offered(corpus: RecipeCorpusStore) -> set[str]:
    candidates = sample_corpus_candidates(
        corpus,
        pantry=[],
        dietary_flags=[TREE_NUT_FREE],
        max_total_time_mins=None,
        exclude_external_ids=[],
        rng=random.Random(0),
        sample_size=25,
    )
    return {candidate.external_id for candidate in candidates}
