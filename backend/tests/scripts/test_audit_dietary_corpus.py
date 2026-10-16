"""The pure parts of the corpus audit harness (#159): the deterministic regex signal, how three signals
become ground truth, confusion counts, the zero-false-negative threshold, and the disagreements report."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest
from pydantic import SecretStr
from scripts import audit_dietary_corpus as audit

from glean.decisions import DECISION_MODEL, DecisionClient
from glean.meal_plan.dietary_decisions import dietary_questions
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


class _CountingDecisionApi:
    def __init__(self) -> None:
        self.requests = 0

    def client(self) -> DecisionClient:
        return DecisionClient(api_key=SecretStr("sk-or-test"), transport=httpx.MockTransport(self._handle))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests += 1
        questions = json.loads(request.content)["questions"]
        return httpx.Response(
            200,
            json={
                "id": "gen-dec-test",
                "model": f"{DECISION_MODEL}-20261014",
                "provider": "TypeSafe",
                "answers": {name: {"type": "noul", "noul": 0.25} for name in questions},
                "usage": {"input_tokens": 10, "output_tokens": 2, "cost": 0.00001},
            },
        )


def _audit_dir(tmp_path: Path) -> Path:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path / "corpus"))
    for external_id in ("rec_a", "rec_b"):
        corpus.save(
            StoredRecipe(
                external_id=external_id,
                title=external_id,
                ingredients=[StoredIngredient(canonical_name="Basil", quantity=1, unit="each")],
            )
        )
    return tmp_path


def test_decision_scoring_resumes_without_requests_when_the_criteria_are_unchanged(tmp_path: Path) -> None:
    data_dir = _audit_dir(tmp_path)
    api = _CountingDecisionApi()
    audit.run_decisions(data_dir, api.client())
    first = api.requests

    audit.run_decisions(data_dir, api.client())

    assert (first, api.requests) == (2, 2)


def test_decision_scoring_asks_again_when_a_flags_criteria_text_changes(tmp_path: Path) -> None:
    data_dir = _audit_dir(tmp_path)
    api = _CountingDecisionApi()
    audit.run_decisions(data_dir, api.client())
    questions = dietary_questions()
    nut_free = questions["nut-free"]
    questions["nut-free"] = nut_free.model_copy(update={"instructions": nut_free.instructions + " Korma counts."})

    audit.run_decisions(data_dir, api.client(), questions=questions)

    assert api.requests == 4


def test_decision_scoring_asks_again_when_a_recipe_changes(tmp_path: Path) -> None:
    data_dir = _audit_dir(tmp_path)
    api = _CountingDecisionApi()
    audit.run_decisions(data_dir, api.client())
    RecipeCorpusStore(FilesystemBlobStore(data_dir / "corpus")).save(
        StoredRecipe(
            external_id="rec_a",
            title="rec_a",
            ingredients=[StoredIngredient(canonical_name="Korma paste", quantity=1, unit="each")],
        )
    )

    audit.run_decisions(data_dir, api.client())

    assert api.requests == 3


def test_disagreements_count_recipes_a_judge_says_contain_nuts_that_the_decision_keeps() -> None:
    signals = {
        "r1": audit.Signals(judges={"a": "breaks", "b": "fine"}, regex=False, probability=0.05),
        "r2": audit.Signals(judges={"a": "breaks", "b": "unsure"}, regex=False, probability=0.9),
        "r3": audit.Signals(judges={"a": "fine", "b": "unsure"}, regex=False, probability=0.05),
        "r4": audit.Signals(judges={"a": "breaks", "b": "breaks"}, regex=True, probability=0.05),
    }

    assert audit.judge_flagged_but_kept(signals, threshold=0.12) == ["r1"]


def test_a_maintainer_label_overrides_the_judges_and_the_regex() -> None:
    both_judges_say_breaks = audit.Signals(judges={"a": "breaks", "b": "breaks"}, regex=True, probability=0.9)
    labelled = next(iter(audit.MAINTAINER_NUT_FREE_LABELS))

    assert audit.resolve_truth("nut-free", labelled, ["Rice"], both_judges_say_breaks) == "fine"
    assert audit.resolve_truth("nut-free", "rec_unlabelled", ["Rice"], both_judges_say_breaks) == "breaks"


def test_the_maintainers_seventeen_labels_are_all_fine_after_the_korma_and_tikka_correction() -> None:
    assert list(audit.MAINTAINER_NUT_FREE_LABELS.values()) == ["fine"] * 17
    assert {"rec_9549ace7527cd5ff", "rec_96e4c5716655075c"} <= set(audit.MAINTAINER_NUT_FREE_LABELS)


def test_without_a_label_the_three_signals_decide_truth_and_curry_pastes_get_no_special_treatment() -> None:
    judges_fine = audit.Signals(judges={"a": "fine", "b": "fine"}, regex=False, probability=0.0)
    unsure = audit.Signals({"a": "fine", "b": "unsure"}, False, 0)

    assert audit.resolve_truth("nut-free", "rec_x", ["Patak's Korma Paste"], judges_fine) == "fine"
    assert audit.resolve_truth("nut-free", "rec_x", ["Tikka Masala Paste"], judges_fine) == "fine"
    assert audit.resolve_truth("nut-free", "rec_x", ["Rice"], unsure) is None


def test_the_threshold_table_reports_errors_and_the_extreme_scores() -> None:
    labelled = [("a", "breaks", 0.9), ("b", "breaks", 0.3), ("c", "fine", 0.7), ("d", "fine", 0.1)]

    rows = audit.threshold_table(labelled, [0.2, 0.5])

    assert [(r.threshold, r.false_negatives, r.false_positives, r.safe, r.unsafe) for r in rows] == [
        (0.2, 0, 1, 2, 2),
        (0.5, 1, 1, 2, 2),
    ]
    assert (rows[0].lowest_unsafe, rows[0].highest_safe) == (0.3, 0.7)
