"""The stored answer (ADR 0025, widened in V5): a probability, and for a labelled question a value.

Seams: `RecipeAnswer` itself (what a store holds and a JSONL line or DynamoDB item carries), the blob
answers file's bytes, and the DynamoDB item shape. The dietary answers written before V5 are the compatibility
contract: their lines and items must be exactly what they were, so nothing they computed is invalidated.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.answers import DIETARY_DECISIONS_KEY, RecipeAnswer, dietary_question
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.dynamo_corpus import _answer_from_row, answer_item

COMPUTED_AT = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


def test_a_dietary_answer_is_its_probability_and_carries_no_value() -> None:
    answer = _dietary("rec_a", "vegan", 0.02)

    assert (answer.value, answer.flag) == (None, "vegan")


def test_a_labelled_answer_stores_its_value_alongside_the_probability_that_decided_it() -> None:
    answer = _labelled("rec_a", "attribute:cuisine", 0.86, "thai")

    assert (answer.value, answer.probability) == ("thai", 0.86)


def test_a_labelled_answer_below_its_bar_stores_unsure_rather_than_nothing() -> None:
    assert _labelled("rec_a", "attribute:cuisine", 0.61, "unsure").value == "unsure"


def test_a_labelled_question_must_carry_a_value() -> None:
    # An answer with no value would read as current while saying nothing, so the shape refuses it.
    with pytest.raises(ValidationError, match="must carry a value"):
        RecipeAnswer(
            recipe_id="rec_a",
            question="attribute:cuisine",
            probability=0.9,
            model="typesafe/jev-1.14-20261014",
            content_hash="c" * 64,
            criteria_hash="d" * 64,
            computed_at=COMPUTED_AT,
        )


def test_a_legacy_dietary_line_still_reads_and_is_a_valid_dietary_answer() -> None:
    line = json.dumps(
        {
            "recipe_id": "rec_a",
            "flag": "Tree-Nut-Free",
            "probability": 0.3,
            "model": "typesafe/jev-1.14-20261014",
            "content_hash": "b" * 64,
            "criteria_hash": "c" * 64,
            "computed_at": COMPUTED_AT.isoformat(),
        }
    )

    answer = RecipeAnswer.model_validate_json(line)

    assert (answer.question, answer.flag, answer.value, answer.probability) == (
        "dietary:tree-nut-free",
        "tree-nut-free",
        None,
        0.3,
    )


def test_a_dumped_dietary_answer_gains_no_null_value_field() -> None:
    payload = json.loads(_dietary("rec_a", "vegan", 0.02).model_dump_json(exclude_none=True))

    assert "value" not in payload
    assert payload["question"] == "dietary:vegan"
    assert payload["flag"] == "vegan"


def test_the_blob_answers_file_is_unchanged_for_a_dietary_answer_written_before_v5(tmp_path) -> None:
    """A pre-V5 line read through the seam and written back is byte-identical: no data loss, no churn."""
    store = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    legacy = json.dumps(
        {
            "recipe_id": "rec_a",
            "question": "dietary:vegan",
            "probability": 0.02,
            "model": "typesafe/jev-1.14-20261014",
            "content_hash": "b" * 64,
            "criteria_hash": "c" * 64,
            "computed_at": "2026-10-22T12:00:00Z",  # what `model_dump_json` writes
            "flag": "vegan",
        },
        separators=(",", ":"),  # what `RecipeAnswer.model_dump_json` writes
    )
    (tmp_path / DIETARY_DECISIONS_KEY).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / DIETARY_DECISIONS_KEY).write_text(legacy + "\n")

    store.save_answers(store.answers())

    assert (tmp_path / DIETARY_DECISIONS_KEY).read_text() == legacy + "\n"


def test_a_labelled_answer_round_trips_through_the_blob_answers_file(tmp_path) -> None:
    store = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    answers = [_dietary("rec_a", "vegan", 0.02), _labelled("rec_a", "attribute:main_protein", 0.83, "chicken")]

    store.save_answers(answers)

    assert store.answers() == sorted(answers, key=lambda answer: (answer.recipe_id, answer.question))


def test_a_dietary_answer_item_is_exactly_the_item_written_before_v5() -> None:
    item = answer_item(_dietary("rec_a", "vegan", 0.02))

    assert set(item) == {
        "pk",
        "sk",
        "recipe_id",
        "question",
        "probability",
        "model",
        "content_hash",
        "criteria_hash",
        "computed_at",
    }


def test_a_labelled_answer_item_carries_its_value_and_reads_back() -> None:
    item = answer_item(_labelled("rec_a", "attribute:active_time:bucket", 0.81, "15-30"))

    assert item["value"] == "15-30"
    assert _answer_from_row(_row(item)) == _labelled("rec_a", "attribute:active_time:bucket", 0.81, "15-30")


def test_a_pre_v5_answer_row_reads_with_no_value() -> None:
    row = _row(answer_item(_dietary("rec_a", "vegan", 0.02)))
    row.pop("value", None)

    assert _answer_from_row(row).value is None


def _row(item: dict) -> dict:
    """The item as DynamoDB hands it back: nested attribute types would be unwrapped by boto3 already."""
    return dict(item)


def _dietary(recipe_id: str, flag: str, probability: float) -> RecipeAnswer:
    return RecipeAnswer(
        recipe_id=recipe_id,
        question=dietary_question(flag),
        probability=probability,
        model="typesafe/jev-1.14-20261014",
        content_hash="b" * 64,
        criteria_hash="c" * 64,
        computed_at=COMPUTED_AT,
    )


def _labelled(recipe_id: str, question: str, probability: float, value: str) -> RecipeAnswer:
    return RecipeAnswer(
        recipe_id=recipe_id,
        question=question,
        probability=probability,
        value=value,
        model="typesafe/jev-1.14-20261014",
        content_hash="b" * 64,
        criteria_hash="e" * 64,
        computed_at=COMPUTED_AT,
    )
