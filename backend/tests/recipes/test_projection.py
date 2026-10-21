"""The S3 projection planning reads in dynamo mode: its document, codec and store seam."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime

import pytest

from glean.recipes.answers import RecipeAnswer, content_fingerprint, dietary_question
from glean.recipes.corpus import recipe_blob_key
from glean.recipes.projection import (
    PROJECTION_KEY,
    FilesystemProjectionStore,
    InMemoryProjectionStore,
    ProjectedRecipe,
    ProjectionError,
    RecipeProjection,
    build_projection,
    dumps,
    loads,
)
from glean.recipes.search_index import RecipeSummary
from tests.recipes.corpus_fixtures import synthetic_corpus, synthetic_recipe

COMPUTED_AT = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


def _answer(recipe_id: str, flag: str, probability: float = 0.02) -> RecipeAnswer:
    recipe = next(r for r in synthetic_corpus() if r.external_id == recipe_id)
    return RecipeAnswer(
        recipe_id=recipe_id,
        question=dietary_question(flag),
        probability=probability,
        model="typesafe/jev-1.14-20261014",
        content_hash=content_fingerprint(recipe.title, [i.canonical_name for i in recipe.ingredients]),
        criteria_hash="a" * 64,
        computed_at=COMPUTED_AT,
    )


def test_projection_round_trips_through_gzip_and_json() -> None:
    projection = build_projection(synthetic_corpus(), [_answer("rec_tomato_pasta", "vegan")])

    restored = loads(dumps(projection))

    assert restored == projection
    assert [summary.title for summary in restored.summaries()] == [
        "Bean Tacos",
        "Chicken Curry",
        "Tomato Pasta",
    ]


def test_projection_bytes_are_deterministic_so_an_unchanged_rebuild_writes_nothing() -> None:
    answers = [_answer("rec_tomato_pasta", "vegan")]

    first = dumps(build_projection(synthetic_corpus(), answers))
    second = dumps(build_projection(list(reversed(synthetic_corpus())), answers))

    assert first == second
    assert json.loads(gzip.decompress(first))["version"] == 1


def test_projection_carries_each_summary_with_its_blob_key_and_room_for_attributes() -> None:
    projection = build_projection([synthetic_recipe("rec_x", title="X", ingredients=["rice"])], [])

    recipe = projection.by_id("rec_x")

    assert recipe is not None
    assert recipe.summary == RecipeSummary(
        external_id="rec_x",
        key=recipe_blob_key("rec_x"),
        title="X",
        difficulty="Easy",
        total_time_mins=25,
        ingredient_names=["rice"],
    )
    assert recipe.attributes == {}


def test_projection_drops_an_answer_whose_recipe_has_changed_since_it_was_asked() -> None:
    stale = _answer("rec_tomato_pasta", "vegan").model_copy(update={"content_hash": "0" * 64})
    current = _answer("rec_tomato_pasta", "peanut-free")
    unknown_recipe = _answer("rec_tomato_pasta", "nut-free").model_copy(update={"recipe_id": "rec_gone"})

    projection = build_projection(synthetic_corpus(), [stale, current, unknown_recipe])

    answered = projection.by_id("rec_tomato_pasta")
    assert answered is not None
    assert [answer.question for answer in answered.answers] == ["dietary:peanut-free"]
    assert projection.by_id("rec_gone") is None


def test_a_projection_with_one_recipe_replaced_keeps_the_others_and_stays_sorted() -> None:
    projection = build_projection(synthetic_corpus(), [])
    replacement = ProjectedRecipe(
        summary=RecipeSummary(external_id="rec_chicken_curry", key="rec_chicken_curry.json", title="Renamed")
    )

    updated = projection.with_recipe(replacement)

    assert [recipe.summary.external_id for recipe in updated.recipes] == [
        "rec_bean_tacos",
        "rec_chicken_curry",
        "rec_tomato_pasta",
    ]
    replaced = updated.by_id("rec_chicken_curry")
    assert replaced is not None
    assert replaced.summary.title == "Renamed"


def test_a_legacy_dietary_jsonl_line_reads_through_the_answer_seam() -> None:
    line = json.dumps(
        {
            "recipe_id": "rec_tomato_pasta",
            "flag": "Tree-Nut-Free",
            "probability": 0.3,
            "model": "typesafe/jev-1.14-20261014",
            "content_hash": "b" * 64,
            "criteria_hash": "c" * 64,
            "computed_at": COMPUTED_AT.isoformat(),
        }
    )

    answer = RecipeAnswer.model_validate_json(line)

    assert (answer.question, answer.flag) == ("dietary:tree-nut-free", "tree-nut-free")


def test_a_dumped_dietary_answer_still_carries_the_flag_a_pre_f1_reader_needs() -> None:
    payload = json.loads(_answer("rec_tomato_pasta", "vegan").model_dump_json())

    assert payload["flag"] == "vegan"
    assert payload["question"] == "dietary:vegan"


def test_the_filesystem_projection_store_reads_back_what_it_wrote(tmp_path) -> None:
    store = FilesystemProjectionStore(tmp_path)

    assert store.read() is None

    store.write(b"{}")

    assert store.read() == b"{}"
    assert (tmp_path / PROJECTION_KEY).exists()


def test_the_in_memory_projection_store_starts_empty() -> None:
    store = InMemoryProjectionStore()

    assert store.read() is None

    store.write(b"{}")

    assert store.read() == b"{}"


def test_a_projection_loads_from_a_hand_built_document(tmp_path) -> None:
    document = RecipeProjection(recipes=[])

    loads(dumps(document))

    assert RecipeProjection.model_validate_json(document.model_dump_json()) == document


def test_a_malformed_projection_document_raises_rather_than_silently_emptying_planning() -> None:
    with pytest.raises(ProjectionError, match="projection"):
        loads(gzip.compress(b'{"version": 2, "recipes": []}'))
