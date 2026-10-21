"""The owner-run corpus migration: idempotent, resumable, paced, and refused on a prod table."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from scripts import migrate_recipe_corpus
from tests.conftest import RECIPES_TABLE_NAME
from tests.recipes.corpus_fixtures import synthetic_corpus
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
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.dynamo_corpus import DynamoCorpusBackend
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
    assert "Projection: 3 recipes, written=True" in out
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
    assert "missing" not in out
    assert [recipe.summary.external_id for recipe in _projection(projections).recipes] == [
        "rec_bean_tacos",
        "rec_chicken_curry",
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


def test_one_recipe_costs_its_body_at_transactional_rates() -> None:
    recipe = synthetic_corpus()[0]

    body_kb = len(recipe.model_dump_json().encode()) // 1024

    assert migrate_recipe_corpus.recipe_wcu(recipe) == 2 * (body_kb + 1) + 2


def _items(table: Any) -> list[dict[str, Any]]:
    return sorted(table.scan()["Items"], key=lambda row: (row["pk"], row["sk"]))


def _projection(projections: InMemoryProjectionStore) -> RecipeProjection:
    assert projections.data is not None
    return loads(projections.data)
