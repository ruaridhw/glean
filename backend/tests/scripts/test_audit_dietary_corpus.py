"""The pure parts of the corpus audit harness (#159): the deterministic regex signal, how three signals
become ground truth, confusion counts, the zero-false-negative threshold, and the disagreements report."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from scripts import audit_dietary_corpus as audit

from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("flag", "ingredients", "excluded"),
    [
        ("vegetarian", ["chicken thigh", "tomato"], True),
        ("vegetarian", ["vegan mince", "tomato"], False),
        ("vegan", ["free range eggs"], True),
        ("vegan", ["coconut milk", "oat milk"], False),
        ("dairy-free", ["Cheddar Cheese"], True),
        ("gluten-free", ["rice noodles", "cornflour"], False),
        ("gluten-free", ["soy sauce"], True),
        ("nut-free", ["pine nuts"], True),
        ("nut-free", ["nutmeg", "coconut milk"], False),
        ("nut-free", ["nut-free pesto"], False),
    ],
)
def test_the_frozen_regex_signal_excludes_what_the_deleted_rules_excluded(flag, ingredients, excluded) -> None:
    assert audit.regex_excludes(flag, ingredients) is excluded


@pytest.mark.parametrize(
    ("judges", "regex", "truth"),
    [
        (["breaks", "breaks"], True, "breaks"),
        (["fine", "fine"], False, "fine"),
        (["breaks", "breaks"], False, None),
        (["breaks", "fine"], True, None),
        (["unsure", "unsure"], False, None),
        (["fine", "fine"], True, None),
    ],
)
def test_ground_truth_needs_both_judges_and_the_regex_to_agree(judges, regex, truth) -> None:
    assert audit.ground_truth(judges, regex) == truth


def test_confusion_counts_kept_unsafe_recipes_as_false_negatives_and_excluded_safe_ones_as_false_positives() -> None:
    labelled = [
        ("a", "breaks", 0.9),  # excluded, right
        ("b", "breaks", 0.3),  # kept: false negative
        ("c", "fine", 0.7),  # excluded: false positive
        ("d", "fine", 0.1),  # kept, right
        ("e", "fine", 0.5),  # at threshold: excluded, false positive
    ]

    result = audit.confusion(labelled, threshold=0.5)

    assert (result.false_negatives, result.false_positives, result.true_positives, result.true_negatives) == (
        ["b"],
        ["c", "e"],
        1,
        1,
    )


def test_the_zero_false_negative_threshold_is_the_lowest_probability_of_an_unsafe_recipe() -> None:
    labelled = [("a", "breaks", 0.9), ("b", "breaks", 0.3), ("c", "fine", 0.7), ("d", "fine", 0.1), ("e", "fine", 0.3)]

    needed = audit.zero_false_negative_threshold(labelled)

    assert needed.threshold == 0.3
    assert needed.false_positives == ["c", "e"]
    assert audit.confusion(labelled, threshold=needed.threshold).false_negatives == []


def test_zero_false_negative_threshold_without_unsafe_recipes_excludes_nothing() -> None:
    needed = audit.zero_false_negative_threshold([("a", "fine", 0.4)])

    assert (needed.threshold, needed.false_positives) == (None, [])


def test_disagreements_are_the_recipes_where_any_signal_differs_and_carry_every_verdict() -> None:
    recipes = {
        "r1": audit.AuditRecipe("r1", "Satay Noodles", ["noodles", "peanut butter"]),
        "r2": audit.AuditRecipe("r2", "Tomato Pasta", ["pasta", "tomato"]),
        "r3": audit.AuditRecipe("r3", "Mystery Bar", ["oat bar"]),
    }
    verdicts = {
        "r1": audit.Signals(judges={"a": "breaks", "b": "breaks"}, regex=True, probability=0.97),
        "r2": audit.Signals(judges={"a": "fine", "b": "fine"}, regex=False, probability=0.05),
        "r3": audit.Signals(judges={"a": "breaks", "b": "unsure"}, regex=False, probability=0.2),
    }

    report = audit.render_disagreements(recipes, verdicts, flag="nut-free")

    assert "Mystery Bar" in report
    assert "oat bar" in report
    assert "a: breaks" in report
    assert "b: unsure" in report
    assert "0.20" in report
    assert "Satay Noodles" not in report
    assert "Tomato Pasta" not in report


def test_recipes_load_from_a_synced_corpus_directory_in_id_order(tmp_path: Path) -> None:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for external_id, title in (("rec_b", "Second"), ("rec_a", "First")):
        corpus.save(
            StoredRecipe(
                external_id=external_id,
                title=title,
                ingredients=[StoredIngredient(canonical_name="Basil", quantity=1, unit="each")],
            )
        )
    (tmp_path / "_index.json").write_text("{}")

    recipes = audit.load_recipes(tmp_path)

    assert [(r.recipe_id, r.title, r.ingredient_names) for r in recipes] == [
        ("rec_a", "First", ["Basil"]),
        ("rec_b", "Second", ["Basil"]),
    ]


def test_a_judge_reply_is_parsed_into_one_verdict_per_flag() -> None:
    reply = json.dumps({flag: {"verdict": "fine", "culprit": None} for flag in audit.FLAGS})

    assert audit.parse_judge_reply(reply) == dict.fromkeys(audit.FLAGS, "fine")


@pytest.mark.parametrize(
    "reply",
    [
        "not json",
        json.dumps({"vegan": {"verdict": "fine"}}),
        json.dumps({f: {"verdict": "maybe"} for f in audit.FLAGS}),
    ],
)
def test_a_malformed_judge_reply_is_rejected(reply) -> None:
    with pytest.raises(audit.JudgeReplyError):
        audit.parse_judge_reply(reply)


def test_disagreement_rows_say_what_each_configuration_does_with_the_recipe() -> None:
    recipes = {"r1": audit.AuditRecipe("r1", "Mystery Bar", ["oat bar"])}
    signals = {
        "r1": audit.Signals(
            judges={"a": "breaks", "b": "fine"}, regex=False, probability=0.9, baseline_probability=0.05
        )
    }

    report = audit.render_disagreements(recipes, signals, flag="nut-free", thresholds=(0.12, 0.12))

    assert "Excluded by #161: yes" in report
    assert "Excluded by #145: NO" in report
    assert "0.05" in report


def test_the_old_regex_alone_excludes_under_the_baseline_even_when_its_decision_is_low() -> None:
    found = audit.Signals(judges={}, regex=True, probability=0.0, baseline_probability=0.0)

    assert audit.excluded_by_regex_or_baseline_decision(found, 0.5) is True
    assert audit.excluded_by_decision(found, 0.5) is False
