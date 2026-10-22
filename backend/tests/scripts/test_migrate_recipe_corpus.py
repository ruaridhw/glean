"""The owner-run corpus migration: idempotent, resumable, paced, and refused on a prod table."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from scripts import migrate_recipe_corpus
from tests.conftest import RECIPES_TABLE_NAME
from tests.recipes.corpus_fixtures import synthetic_corpus, synthetic_recipe
from tests.recipes.fake_projection import InMemoryProjectionStore

from glean.decisions import DECISION_MODEL
from glean.meal_plan.dietary_decisions import (
    DietaryDecision,
    DietaryDecisionStore,
    content_fingerprint,
    dietary_questions,
    question_hash,
)
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes import dynamo_corpus
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.dynamo_corpus import DynamoCorpusBackend, item_write_units, recipe_item, source_item
from glean.recipes.projection import loads

if TYPE_CHECKING:
    from pathlib import Path

    from glean.recipes.projection import RecipeProjection

COMPUTED_AT = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


@pytest.fixture
def source(tmp_path: Path) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path / "corpus"))
    for recipe in synthetic_corpus():
        corpus.save(recipe)
    DietaryDecisionStore(corpus.store).save(
        [
            DietaryDecision(
                recipe_id=recipe.external_id,
                flag="tree-nut-free",
                probability=0.02,
                model=f"{DECISION_MODEL}-20261014",
                content_hash=content_fingerprint(
                    recipe.title, [ingredient.canonical_name for ingredient in recipe.ingredients]
                ),
                criteria_hash=question_hash(dietary_questions()["tree-nut-free"]),
                computed_at=COMPUTED_AT,
            )
            for recipe in synthetic_corpus()
        ]
    )
    return corpus


@pytest.fixture
def projections() -> InMemoryProjectionStore:
    return InMemoryProjectionStore()


@pytest.fixture
def backend(recipes_table: Any, projections: InMemoryProjectionStore) -> DynamoCorpusBackend:
    return DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=projections)


def _run(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    predictions: InMemoryProjectionStore,
    *extra: str,
) -> int:
    return migrate_recipe_corpus.main(
        [
            "--table",
            RECIPES_TABLE_NAME,
            "--local",
            str(tmp_path),
            "--checkpoint",
            str(tmp_path / "checkpoint.json"),
            *extra,
        ],
        backend=backend,
        corpus_source=source,
        projection_store=predictions,
    )


def test_a_dry_run_reports_the_plan_and_writes_nothing(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
    recipes_table: Any,
    capsys: pytest.CaptureFixture,
) -> None:
    assert _run(tmp_path, backend, source, projections, "--dry-run") == 0

    out = capsys.readouterr().out
    assert "Migration plan: 3 recipes, 3 answers" in out
    assert "write units" in out
    assert "Dry run: wrote nothing." in out
    assert recipes_table.scan()["Items"] == []


def test_the_migration_writes_every_recipe_its_answers_and_the_projection(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
    capsys: pytest.CaptureFixture,
) -> None:
    assert _run(tmp_path, backend, source, projections) == 0

    out = capsys.readouterr().out
    assert "Written this run: 3 recipes, 3 answers" in out
    assert "Verified in the table: 3/3 recipes (the corpus is complete)" in out
    assert "Projection: 3 recipes" in out
    assert "not rebuilt" not in out
    for recipe in synthetic_corpus():
        assert backend.get(recipe.external_id) == recipe
        assert backend.get_by_source_url(recipe.source_url) == recipe
    assert {answer.recipe_id for answer in backend.answers()} == {
        "rec_tomato_pasta",
        "rec_chicken_curry",
        "rec_bean_tacos",
    }
    assert [recipe.summary.external_id for recipe in _projection(projections).recipes] == [
        "rec_bean_tacos",
        "rec_chicken_curry",
        "rec_tomato_pasta",
    ]
    # Answers are written before their recipe, so even a partial projection carries the decisions.
    assert len(_projection(projections).answers()) == 3


def test_a_second_run_writes_nothing_and_leaves_the_same_items_and_projection(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
    recipes_table: Any,
    capsys: pytest.CaptureFixture,
) -> None:
    _run(tmp_path, backend, source, projections)
    items = _items(recipes_table)
    projection = projections.read()
    writes = projections.writes
    capsys.readouterr()

    assert _run(tmp_path, backend, source, projections) == 0

    out = capsys.readouterr().out
    assert "Written this run: 0 recipes, 0 answers" in out
    assert "written=False" in out
    assert _items(recipes_table) == items
    assert projections.read() == projection
    assert projections.writes == writes


def test_a_resumed_run_skips_the_recipes_the_checkpoint_names(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
    capsys: pytest.CaptureFixture,
) -> None:
    assert _run(tmp_path, backend, source, projections, "--limit", "1") == 0
    capsys.readouterr()

    assert _run(tmp_path, backend, source, projections) == 0

    out = capsys.readouterr().out
    assert "2 recipes, 2 answers (1 already migrated on an earlier run)" in out
    assert "Verified in the table: 3/3 recipes (the corpus is complete)" in out
    assert "MISSING" not in out
    assert [recipe.summary.external_id for recipe in _projection(projections).recipes] == [
        "rec_bean_tacos",
        "rec_chicken_curry",
        "rec_tomato_pasta",
    ]


def test_a_retry_without_a_checkpoint_still_publishes_the_projection(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
    capsys: pytest.CaptureFixture,
) -> None:
    """The interruption case: every row is in the table, but the run that wrote them never checkpointed."""
    _run(tmp_path, backend, source, projections, "--no-checkpoint")
    (tmp_path / "checkpoint.json").unlink(missing_ok=True)
    capsys.readouterr()

    assert _run(tmp_path, backend, source, projections, "--no-checkpoint") == 0

    out = capsys.readouterr().out
    assert "Written this run: 0 recipes, 0 answers" in out
    assert "Verified in the table: 3/3 recipes (the corpus is complete)" in out
    assert "Projection: 3 recipes" in out
    assert "not rebuilt" not in out
    assert len(_projection(projections).recipes) == 3


def test_a_checkpoint_lost_after_an_interruption_still_finishes_the_projection(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
    capsys: pytest.CaptureFixture,
) -> None:
    # One recipe migrated and committed, then the process died before the checkpoint was flushed.
    _run(tmp_path, backend, source, projections, "--limit", "1", "--no-checkpoint")
    capsys.readouterr()

    assert _run(tmp_path, backend, source, projections, "--no-checkpoint") == 0

    out = capsys.readouterr().out
    assert "Verified in the table: 3/3 recipes (the corpus is complete)" in out
    assert "not rebuilt" not in out
    assert [recipe.summary.external_id for recipe in _projection(projections).recipes] == [
        "rec_bean_tacos",
        "rec_chicken_curry",
        "rec_tomato_pasta",
    ]


def test_a_full_run_that_leaves_a_recipe_unverified_exits_non_zero(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
    recipes_table: Any,
    capsys: pytest.CaptureFixture,
) -> None:
    _run(tmp_path, backend, source, projections)
    recipes_table.delete_item(Key={"pk": "RECIPE#rec_bean_tacos", "sk": "RECIPE"})
    capsys.readouterr()

    assert _run(tmp_path, backend, source, projections) == 1

    out = capsys.readouterr().out
    assert "Verified in the table: 2/3 recipes (INCOMPLETE)" in out
    assert "MISSING from the table: 1 recipes" in out


def test_the_pacer_is_charged_for_the_answers_as_well_as_the_recipes(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    elapsed = [0.0]
    original = migrate_recipe_corpus.Pacer.__init__

    def paced(self, rate, *, clock=None, sleep=None):
        original(
            self,
            rate,
            clock=lambda: elapsed[0],
            sleep=lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds),
        )

    monkeypatch.setattr(migrate_recipe_corpus.Pacer, "__init__", paced)

    _run(tmp_path, backend, source, projections, "--wcu-per-second", "4")

    planned = migrate_recipe_corpus._plan(source)
    # Every write (answer items included) is paced, so wall clock is the accounted units over the rate.
    assert elapsed[0] == pytest.approx(planned.wcu / 4)
    assert planned.wcu == sum(
        migrate_recipe_corpus.recipe_wcu(recipe)
        + sum(
            migrate_recipe_corpus.answer_write_units(answer)
            for answer in planned.answers_planned_for(recipe.external_id)
        )
        for recipe in planned.recipes
    )


def test_items_are_sized_by_dynamodb_string_bytes_not_json_encoding() -> None:
    # pk 2 + sk 2 + body 4 attribute-name bytes; values 1 + 1 + 1010 = 1020 bytes, so one unit.
    assert item_write_units({"pk": "x", "sk": "y", "body": "x" * 1010}) == 1
    assert item_write_units({"pk": "x", "sk": "y", "body": "x" * 1015}) == 2
    # A body of JSON text is stored as a plain string: its quotes are not escaped by DynamoDB.
    assert item_write_units({"pk": "x", "sk": "y", "body": '{"a": "b"}' * 100}) == 1


@pytest.mark.parametrize("index", [0, 1, 2])
def test_each_synthetic_recipe_body_and_pointer_costs_one_write_unit(index: int) -> None:
    recipe = synthetic_corpus()[index]

    assert item_write_units(recipe_item(recipe)) == 1
    assert item_write_units(source_item(recipe)) == 1
    assert migrate_recipe_corpus.recipe_wcu(recipe) == 4


def test_the_estimate_counts_the_item_overhead_and_charges_answers(tmp_path: Path, source: RecipeCorpusStore) -> None:
    planned = migrate_recipe_corpus._plan(source)
    recipe = planned.recipes[0]

    assert planned.wcu == sum(
        migrate_recipe_corpus.recipe_wcu(item) + len(planned.answers_planned_for(item.external_id))
        for item in planned.recipes
    )
    assert migrate_recipe_corpus.recipe_wcu(recipe) == 2 * (
        item_write_units(recipe_item(recipe)) + item_write_units(source_item(recipe))
    )
    assert migrate_recipe_corpus.answer_write_units(
        planned.answers_planned_for(recipe.external_id)[0]
    ) == dynamo_corpus.item_write_units(dynamo_corpus.answer_item(planned.answers_planned_for(recipe.external_id)[0]))
    without_url = recipe.model_copy(update={"source_url": None})
    assert migrate_recipe_corpus.recipe_wcu(without_url) == 2 * item_write_units(recipe_item(without_url))


@pytest.mark.parametrize(
    "document",
    [
        "[]",
        '{"owner": "x", "migrated": {"a": 1}}',
        '{"owner": "x", "migrated": [1, 2]}',
        '{"owner": "x"}',
    ],
)
def test_an_unreadable_checkpoint_shape_is_reported_and_the_run_starts_fresh(
    document: str,
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
    capsys: pytest.CaptureFixture,
) -> None:
    (tmp_path / "checkpoint.json").write_text(document)

    assert _run(tmp_path, backend, source, projections) == 0

    out = capsys.readouterr().out
    assert "Ignoring unreadable checkpoint" in out
    assert "Written this run: 3 recipes, 3 answers" in out


def test_a_dry_run_with_reset_checkpoint_does_not_touch_the_checkpoint(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
    capsys: pytest.CaptureFixture,
) -> None:
    _run(tmp_path, backend, source, projections, "--limit", "1")
    checkpoint = tmp_path / "checkpoint.json"
    saved = checkpoint.read_bytes()
    capsys.readouterr()

    assert _run(tmp_path, backend, source, projections, "--dry-run", "--reset-checkpoint") == 0

    assert checkpoint.exists()
    assert checkpoint.read_bytes() == saved


def test_resetting_the_checkpoint_on_a_real_run_starts_from_the_beginning(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
    capsys: pytest.CaptureFixture,
) -> None:
    _run(tmp_path, backend, source, projections, "--no-checkpoint")
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text('{"owner": "glean-recipes-test|x", "migrated": ["rec_bean_tacos"]}')
    capsys.readouterr()

    assert _run(tmp_path, backend, source, projections, "--reset-checkpoint") == 0

    assert "already migrated on an earlier run" not in capsys.readouterr().out


def test_the_summary_states_what_rolling_back_to_blobs_does_and_does_not_restore(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
    capsys: pytest.CaptureFixture,
) -> None:
    _run(tmp_path, backend, source, projections)

    out = capsys.readouterr().out
    assert "as of this migration" in out
    assert "NOT in the blobs" in out
    assert "re-run scripts/compute_dietary_decisions.py" in out


def test_the_final_projection_is_rebuilt_from_the_table_not_from_the_source(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
    capsys: pytest.CaptureFixture,
) -> None:
    """The reviewer's reproduction: a recipe saved and projected while the migration ran must survive it."""
    extra = synthetic_recipe("rec_imported_meanwhile", title="Imported Meanwhile", ingredients=["lentils"])
    DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=projections).save(extra)
    capsys.readouterr()

    assert _run(tmp_path, backend, source, projections) == 0

    ids = sorted(recipe.summary.external_id for recipe in _projection(projections).recipes)
    assert ids == ["rec_bean_tacos", "rec_chicken_curry", "rec_imported_meanwhile", "rec_tomato_pasta"]
    assert "Projection: 4 recipes, written=False" in capsys.readouterr().out


def test_a_migration_over_a_table_that_already_holds_more_than_the_source_keeps_those_recipes(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
) -> None:
    # The table row exists but was never projected: a source-built document would advertise only the source.
    DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=projections).save(
        synthetic_recipe("rec_table_only", title="Table Only", ingredients=["barley"])
    )
    projections.delete()

    assert _run(tmp_path, backend, source, projections) == 0

    assert sorted(recipe.summary.external_id for recipe in _projection(projections).recipes) == [
        "rec_bean_tacos",
        "rec_chicken_curry",
        "rec_table_only",
        "rec_tomato_pasta",
    ]


def test_a_limit_run_leaves_a_consistent_projection_of_what_it_migrated(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
    capsys: pytest.CaptureFixture,
) -> None:
    assert _run(tmp_path, backend, source, projections, "--limit", "2") == 0

    assert "Projection: not rebuilt" in capsys.readouterr().out
    # Each write kept the projection current, so a half-migrated corpus still searches consistently.
    assert [recipe.summary.external_id for recipe in _projection(projections).recipes] == [
        "rec_bean_tacos",
        "rec_chicken_curry",
    ]
    assert {(answer.recipe_id, answer.question) for answer in _projection(projections).answers()} == {
        ("rec_bean_tacos", "dietary:tree-nut-free"),
        ("rec_chicken_curry", "dietary:tree-nut-free"),
    }


def test_a_checkpoint_naming_recipes_a_wiped_table_lost_is_reported(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
    recipes_table: Any,
    capsys: pytest.CaptureFixture,
) -> None:
    _run(tmp_path, backend, source, projections)
    recipes_table.delete_item(Key={"pk": "RECIPE#rec_bean_tacos", "sk": "RECIPE"})
    capsys.readouterr()

    assert _run(tmp_path, backend, source, projections) == 1

    assert "MISSING from the table: 1 recipes" in capsys.readouterr().out


def test_the_migration_refuses_a_prod_table_without_the_owner_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    code = migrate_recipe_corpus.main(["--table", "glean-recipes-prod", "--local", str(tmp_path)])

    assert code == 2
    assert "--i-am-the-owner" in capsys.readouterr().out


def test_a_dry_run_may_look_at_a_prod_table_because_it_writes_nothing(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
) -> None:
    code = migrate_recipe_corpus.main(
        ["--table", "glean-recipes-prod", "--local", str(tmp_path), "--dry-run"],
        backend=backend,
        corpus_source=source,
        projection_store=projections,
    )

    assert code == 0


def test_the_owner_flag_lets_a_prod_table_through(
    tmp_path: Path,
    backend: DynamoCorpusBackend,
    source: RecipeCorpusStore,
    projections: InMemoryProjectionStore,
) -> None:
    code = migrate_recipe_corpus.main(
        ["--table", "glean-recipes-prod", "--local", str(tmp_path), "--i-am-the-owner", "--dry-run"],
        backend=backend,
        corpus_source=source,
        projection_store=projections,
    )

    assert code == 0


def test_the_pacer_holds_the_run_to_the_configured_write_rate() -> None:
    clock = [0.0]
    slept: list[float] = []

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        clock[0] += seconds

    pacer = migrate_recipe_corpus.Pacer(5.0, clock=lambda: clock[0], sleep=sleep)

    pacer.spend(5)
    pacer.spend(10)

    # 15 write units at 5 WCU/s must take three seconds of wall clock, however fast the writes land.
    assert slept == [pytest.approx(1.0), pytest.approx(2.0)]
    assert clock[0] == pytest.approx(3.0)


def _items(table: Any) -> list[dict[str, Any]]:
    return sorted(table.scan()["Items"], key=lambda row: (row["pk"], row["sk"]))


def _projection(projections: InMemoryProjectionStore) -> RecipeProjection:
    assert projections.data is not None
    return loads(projections.data)
