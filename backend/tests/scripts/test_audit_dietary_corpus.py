"""The pure parts of the corpus audit harness (#159): the deterministic regex signal, how three signals
become ground truth, confusion counts, the zero-false-negative threshold, and the disagreements report."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest
from grocery_fixtures import FakePageSource, ocado_product, ocado_search
from pydantic import SecretStr
from scripts import audit_dietary_corpus as audit
from scripts.grocery_ground_truth import ContainsPolicy, Frequency, IngredientVerdict, OcadoReader, retailer_lookup

from glean.decisions import DECISION_MODEL, DecisionClient
from glean.meal_plan.dietary_decisions import dietary_questions
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe

if TYPE_CHECKING:
    from pathlib import Path


TREE_LABELS = audit.MAINTAINER_LABELS["tree-nut-free"]


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
        ("tree-nut-free", ["pine nuts"], True),
        ("tree-nut-free", ["nutmeg", "coconut milk"], False),
        ("tree-nut-free", ["nut-free pesto"], False),
        ("tree-nut-free", ["chicken satay sauce", "peanut butter"], False),
        ("peanut-free", ["chicken satay sauce"], True),
        ("peanut-free", ["peanut butter"], True),
        ("peanut-free", ["pine nuts", "almonds", "coconut milk"], False),
        ("tree-nut-free", ["mixed nut butter"], True),
        ("peanut-free", ["mixed nut butter"], True),
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

    report = audit.render_disagreements(recipes, verdicts, flag="tree-nut-free")

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


def test_a_judge_is_asked_only_about_the_flags_a_stored_judgement_cannot_answer() -> None:
    legacy_fine = {
        "vegetarian": "breaks",
        "vegan": "breaks",
        "dairy-free": "fine",
        "gluten-free": "fine",
        "nut-free": "fine",
    }
    legacy_breaks = {**legacy_fine, "nut-free": "breaks"}
    legacy_unsure = {**legacy_fine, "nut-free": "unsure"}

    assert audit.carried_verdicts(legacy_fine) == {"tree-nut-free": "fine", "peanut-free": "fine"}
    assert audit.flags_to_ask(legacy_fine) == ()
    assert audit.carried_verdicts(legacy_breaks) == {}
    assert audit.flags_to_ask(legacy_breaks) == ("tree-nut-free", "peanut-free")
    assert audit.flags_to_ask(legacy_unsure) == ("tree-nut-free", "peanut-free")
    assert audit.flags_to_ask({}) == audit.FLAGS


def test_a_judge_reply_about_a_subset_of_flags_is_parsed_and_the_schema_asks_for_just_those() -> None:
    flags = ("tree-nut-free", "peanut-free")
    reply = json.dumps({flag: {"verdict": "breaks", "culprit": "x"} for flag in flags})

    assert audit.parse_judge_reply(reply, flags) == {"tree-nut-free": "breaks", "peanut-free": "breaks"}
    assert audit.judge_schema(flags)["required"] == list(flags)


def test_the_judge_instructions_keep_tree_nuts_and_peanuts_apart_and_ignore_may_contain() -> None:
    text = audit._JUDGE_INSTRUCTIONS.casefold()

    assert "- tree-nut-free:" in text
    assert "- peanut-free:" in text
    assert "- nut-free:" not in text
    assert "may contain" in text


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

    report = audit.render_disagreements(recipes, signals, flag="tree-nut-free", thresholds=(0.12, 0.12))

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
    tree_nut_free = questions["tree-nut-free"]
    questions["tree-nut-free"] = tree_nut_free.model_copy(
        update={"instructions": tree_nut_free.instructions + " Korma counts."}
    )

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
    labelled = next(iter(TREE_LABELS))

    assert audit.resolve_truth("tree-nut-free", labelled, ["Rice"], both_judges_say_breaks) == "fine"
    assert audit.resolve_truth("tree-nut-free", "rec_unlabelled", ["Rice"], both_judges_say_breaks) == "breaks"


def test_the_maintainers_labels_were_given_for_tree_nuts_so_peanut_free_has_none() -> None:
    labelled = next(iter(TREE_LABELS))
    both_judges_say_breaks = audit.Signals(judges={"a": "breaks", "b": "breaks"}, regex=True, probability=0.9)
    unsure = audit.Signals(judges={"a": "unsure", "b": "unsure"}, regex=False, probability=0.9)

    assert audit.MAINTAINER_LABELS["peanut-free"] == {}
    assert audit.resolve_truth("peanut-free", labelled, ["Rice"], both_judges_say_breaks) == "breaks"
    assert audit.resolve_truth("peanut-free", labelled, ["Rice"], unsure) is None
    assert audit.resolve_truth("tree-nut-free", labelled, ["Rice"], both_judges_say_breaks) == "fine"


def test_the_maintainers_seventeen_labels_are_all_fine_after_the_korma_and_tikka_correction() -> None:
    assert list(TREE_LABELS.values()) == ["fine"] * 17
    assert {"rec_9549ace7527cd5ff", "rec_96e4c5716655075c"} <= set(TREE_LABELS)


def test_without_a_label_the_three_signals_decide_truth_and_curry_pastes_get_no_special_treatment() -> None:
    judges_fine = audit.Signals(judges={"a": "fine", "b": "fine"}, regex=False, probability=0.0)
    unsure = audit.Signals({"a": "fine", "b": "unsure"}, False, 0)

    assert audit.resolve_truth("tree-nut-free", "rec_x", ["Patak's Korma Paste"], judges_fine) == "fine"
    assert audit.resolve_truth("tree-nut-free", "rec_x", ["Tikka Masala Paste"], judges_fine) == "fine"
    assert audit.resolve_truth("tree-nut-free", "rec_x", ["Rice"], unsure) is None


def test_the_threshold_table_reports_errors_and_the_extreme_scores() -> None:
    labelled = [("a", "breaks", 0.9), ("b", "breaks", 0.3), ("c", "fine", 0.7), ("d", "fine", 0.1)]

    rows = audit.threshold_table(labelled, [0.2, 0.5])

    assert [(r.threshold, r.false_negatives, r.false_positives, r.safe, r.unsafe) for r in rows] == [
        (0.2, 0, 1, 2, 2),
        (0.5, 1, 1, 2, 2),
    ]
    assert (rows[0].lowest_unsafe, rows[0].highest_safe) == (0.3, 0.7)


def _shelf(*, tree_nut=Frequency.RARELY, peanut=Frequency.RARELY, may_contain=Frequency.RARELY) -> IngredientVerdict:
    return IngredientVerdict(
        ingredient="x", status="resolved", retailer="ocado", products_read=7,
        tree_nut=tree_nut, peanut=peanut, may_contain=may_contain,
    )  # fmt: skip


_UNSURE = audit.Signals(judges={"a": "unsure", "b": "unsure"}, regex=False, probability=0.3)
_PESTO_ONLY = lambda name: _shelf(tree_nut=Frequency.USUALLY) if "pesto" in name.casefold() else _shelf()  # noqa: E731


def test_a_retailer_verdict_settles_a_recipe_both_judges_are_unsure_about() -> None:
    def resolve(names: list[str]) -> str | None:
        return audit.resolve_truth("tree-nut-free", "rec_x", names, _UNSURE, lookup=_PESTO_ONLY)

    assert resolve(["Green Pesto", "Pasta"]) == "breaks"
    assert resolve(["Thai Green Curry Paste", "Rice"]) == "fine"


def test_a_retailer_verdict_settles_a_recipe_the_judges_disagree_about() -> None:
    disagree = audit.Signals(judges={"a": "breaks", "b": "fine"}, regex=False, probability=0.3)

    assert audit.resolve_truth("tree-nut-free", "rec_x", ["Green Pesto"], disagree, lookup=lambda _: _shelf()) == "fine"


def test_the_retailer_outranks_a_maintainer_label_where_it_gives_a_definite_answer() -> None:
    fine_label = next(iter(TREE_LABELS))

    truth = audit.resolve_truth("tree-nut-free", fine_label, ["Green Pesto"], _UNSURE, lookup=_PESTO_ONLY)

    assert TREE_LABELS[fine_label] == "fine"
    assert truth == "breaks"


def test_the_maintainer_label_decides_where_the_retailer_cannot() -> None:
    blocked = lambda name: IngredientVerdict(ingredient=name, status="blocked")  # noqa: E731
    fine_label = next(iter(TREE_LABELS))
    unsure_and_unlabelled = audit.resolve_truth("tree-nut-free", "rec_x", ["Green Pesto"], _UNSURE, lookup=blocked)

    assert audit.resolve_truth("tree-nut-free", fine_label, ["Green Pesto"], _UNSURE, lookup=blocked) == "fine"
    assert unsure_and_unlabelled is None


def test_the_retailer_is_not_asked_when_the_judges_agree() -> None:
    asked: list[str] = []

    def shelf(name: str) -> IngredientVerdict:
        asked.append(name)
        return _shelf(tree_nut=Frequency.USUALLY)

    agree = audit.Signals(judges={"a": "fine", "b": "fine"}, regex=False, probability=0.0)

    assert audit.resolve_truth("tree-nut-free", "rec_x", ["Green Pesto"], agree, lookup=shelf) == "fine"
    assert asked == []


def test_an_unresolved_processed_ingredient_stays_unknown_and_never_silently_safe() -> None:
    blocked = lambda name: IngredientVerdict(ingredient=name, status="blocked")  # noqa: E731

    assert audit.resolve_truth("tree-nut-free", "rec_x", ["Green Pesto", "Rice"], _UNSURE, lookup=blocked) is None


def test_one_unsafe_ingredient_breaks_the_recipe_even_when_another_could_not_be_read() -> None:
    def shelf(name: str) -> IngredientVerdict:
        if "pesto" in name.casefold():
            return _shelf(tree_nut=Frequency.USUALLY)
        return IngredientVerdict(ingredient=name, status="not_found")

    assert (
        audit.resolve_truth("tree-nut-free", "rec_x", ["Green Pesto", "Satay Sauce"], _UNSURE, lookup=shelf) == "breaks"
    )


def test_a_name_that_is_not_a_processed_ingredient_is_not_looked_up() -> None:
    asked: list[str] = []

    def shelf(name: str) -> IngredientVerdict:
        asked.append(name)
        return _shelf()

    names = ["Rice", "Milliliter(s) Water for the Sauce"]

    assert audit.resolve_truth("tree-nut-free", "rec_x", names, _UNSURE, lookup=shelf) is None
    assert asked == []


def test_the_contains_policy_changes_what_a_retailer_verdict_means_for_a_recipe() -> None:
    sometimes = lambda _: _shelf(tree_nut=Frequency.SOMETIMES, may_contain=Frequency.USUALLY)  # noqa: E731

    def truth(policy: ContainsPolicy | None) -> str | None:
        return audit.resolve_truth(
            "tree-nut-free", "rec_x", ["Tikka Masala Paste"], _UNSURE, lookup=sometimes, policy=policy
        )

    assert truth(None) == "fine"
    assert truth(ContainsPolicy(minimum=Frequency.SOMETIMES)) == "breaks"
    assert truth(ContainsPolicy(may_contain_counts=True)) == "breaks"


def test_other_flags_never_consult_the_retailer() -> None:
    def shelf(name: str) -> IngredientVerdict:
        raise AssertionError(f"asked about {name}")

    assert audit.resolve_truth("vegan", "rec_x", ["Green Pesto"], _UNSURE, lookup=shelf) is None


def test_the_retailer_section_lists_each_both_unsure_recipe_with_its_shelf_and_the_maintainers_label() -> None:
    labelled = next(iter(TREE_LABELS))
    recipes = {
        labelled: audit.AuditRecipe(labelled, "Korma", ["Korma Curry Paste", "Rice"]),
        "rec_y": audit.AuditRecipe("rec_y", "Pesto pasta", ["Green Pesto"]),
        "rec_z": audit.AuditRecipe("rec_z", "Plain", ["Rice"]),
    }
    signals = {
        labelled: _UNSURE,
        "rec_y": _UNSURE,
        "rec_z": audit.Signals(judges={"a": "fine", "b": "fine"}, regex=False, probability=0.0),
    }

    report = audit.render_retailer_section(recipes, signals, flag="tree-nut-free", lookup=_PESTO_ONLY, policy=None)

    assert "Korma (`" + labelled + "`): retailer fine; maintainer label fine" in report
    assert "Pesto pasta (`rec_y`): retailer breaks; maintainer label none" in report
    assert "Plain" not in report


def _all_safe(name: str) -> IngredientVerdict:
    return _shelf()


@pytest.mark.parametrize(
    ("flag", "names"),
    [
        ("tree-nut-free", ["nut-free pesto", "almonds"]),
        ("tree-nut-free", ["Pesto", "Almonds"]),
        ("tree-nut-free", ["Green Pesto", "Marzipan"]),
        ("peanut-free", ["Teriyaki Sauce", "Peanut Oil"]),
        ("peanut-free", ["Satay Sauce", "Rice"]),
        ("peanut-free", ["Green Pesto", "Peanut Butter"]),
    ],
)
def test_a_safe_processed_ingredient_never_whitewashes_another_ingredient_that_is_itself_an_allergen(
    flag, names
) -> None:
    assert audit.resolve_truth(flag, "rec_x", names, _UNSURE, lookup=_all_safe) == "breaks"


@pytest.mark.parametrize(
    ("flag", "names"),
    [
        ("tree-nut-free", ["Satay Sauce", "Peanut Oil", "Coconut Milk"]),
        ("peanut-free", ["Green Pesto", "Almonds", "Marzipan"]),
    ],
)
def test_an_ingredient_of_the_other_nut_kind_does_not_break_the_recipe(flag, names) -> None:
    assert audit.resolve_truth(flag, "rec_x", names, _UNSURE, lookup=_all_safe) == "fine"


def test_a_peanut_shelf_breaks_a_peanut_free_recipe_and_leaves_a_tree_nut_free_one_fine() -> None:
    satay_shelf = lambda _: _shelf(peanut=Frequency.USUALLY)  # noqa: E731

    assert audit.resolve_truth("peanut-free", "rec_x", ["Satay Sauce"], _UNSURE, lookup=satay_shelf) == "breaks"
    assert audit.resolve_truth("tree-nut-free", "rec_x", ["Satay Sauce"], _UNSURE, lookup=satay_shelf) == "fine"


def test_a_tree_nut_shelf_breaks_a_tree_nut_free_recipe_and_leaves_a_peanut_free_one_fine() -> None:
    assert audit.resolve_truth("tree-nut-free", "rec_x", ["Green Pesto"], _UNSURE, lookup=_PESTO_ONLY) == "breaks"
    assert audit.resolve_truth("peanut-free", "rec_x", ["Green Pesto"], _UNSURE, lookup=_PESTO_ONLY) == "fine"


def test_a_nut_free_label_in_a_name_is_not_a_nut() -> None:
    assert (
        audit.resolve_truth("tree-nut-free", "rec_x", ["Nut-Free Pesto", "Coconut Milk"], _UNSURE, lookup=_all_safe)
        == "fine"
    )


def test_a_recipe_is_fine_only_when_every_processed_ingredient_is_settled_safe() -> None:
    def shelf(name: str) -> IngredientVerdict:
        return _shelf() if "pesto" in name.casefold() else IngredientVerdict(ingredient=name, status="insufficient")

    names = ["Green Pesto", "Korma Paste", "Rice"]

    assert audit.resolve_truth("tree-nut-free", "rec_x", names, _UNSURE, lookup=shelf) is None


def test_the_audits_retailer_lookup_carries_the_selected_policy_so_incomplete_samples_stay_unknown() -> None:
    brands = ["Acme", "Bravo", "Corner", "Delta", "Echo"]
    pages = {
        f"https://www.ocado.com/products/p{i}/{i}": ocado_product(
            f"{b} Korma Paste", None if i == 4 else "Water, Spices"
        )
        for i, b in enumerate(brands)
    }
    pages["https://www.ocado.com/search?q=Korma%20Paste"] = ocado_search(
        *((f"{b} Korma Paste", f"/products/p{i}/{i}") for i, b in enumerate(brands))
    )
    names = ["Korma Paste", "Rice"]

    def truth(policy: ContainsPolicy | None) -> str | None:
        lookup = retailer_lookup([OcadoReader(FakePageSource(pages))], policy=policy)
        return audit.resolve_truth("tree-nut-free", "rec_x", names, _UNSURE, lookup=lookup, policy=policy)

    assert truth(None) == "fine"
    assert truth(ContainsPolicy(minimum=Frequency.SOMETIMES)) is None


def test_a_one_product_shelf_for_a_food_possessive_leaves_the_recipe_unknown_not_fine() -> None:
    shop = FakePageSource(
        {
            "https://www.ocado.com/search?q=shepherd%27s%20seasoning": ocado_search(
                ("Shepherd's Seasoning", "/products/s/1")
            ),
            "https://www.ocado.com/products/s/1": ocado_product("Shepherd's Seasoning", "Salt, Herbs"),
        }
    )
    lookup = retailer_lookup([OcadoReader(shop)])

    truth = audit.resolve_truth("tree-nut-free", "rec_x", ["shepherd's seasoning", "Rice"], _UNSURE, lookup=lookup)

    assert lookup("shepherd's seasoning").status == "insufficient"
    assert truth is None


def test_the_report_scores_each_nut_flag_on_its_own_and_writes_a_disagreement_file_for_each(tmp_path: Path) -> None:
    data_dir = _audit_dir(tmp_path)
    api = _CountingDecisionApi()
    baseline = {
        **{flag: question for flag, question in dietary_questions().items() if flag not in audit.NUT_FLAGS},
        "nut-free": dietary_questions()["tree-nut-free"],
    }
    audit.run_decisions(data_dir, api.client())
    audit.run_decisions(data_dir, api.client(), questions=baseline, name="decisions-145")
    for judge in audit.JUDGES:
        entries = {rid: {"verdicts": dict.fromkeys(audit.FLAGS, "fine"), "cost": 0.0} for rid in ("rec_a", "rec_b")}
        (data_dir / f"judge-{judge}.json").write_text(json.dumps({"entries": entries}))

    audit.run_report(data_dir, baseline_questions=baseline, baseline_thresholds=(0.12, 0.5))

    report = (data_dir / "report.md").read_text()
    assert "## tree-nut-free threshold table" in report
    assert "## peanut-free threshold table" in report
    assert "## nut-free:" not in report
    assert "## tree-nut-free: 2 agreed" in report
    assert "#145" not in report.split("## tree-nut-free:")[1].split("## ")[0]
    assert (data_dir / "tree-nut-free-disagreements.md").exists()
    assert (data_dir / "peanut-free-both-unsure.md").exists()


_CHILLI_OIL_RECIPE = ["Crispy Chilli Oil", "Soy Sauce", "Chicken Thigh", "Cherry Tomatoes"]


def _shelf_where(**by_product: IngredientVerdict):
    def lookup(name: str) -> IngredientVerdict:
        return next((v for key, v in by_product.items() if key in name.casefold().replace(" ", "_")), _shelf())

    return lookup


@pytest.mark.parametrize("name", ["Chilli Crisp", "chilli crisp", "Crunchy Chilli Crisp", "Crispy Chilli Oil"])
def test_a_chilli_crisp_follows_what_its_shelf_lists_with_no_named_exception(name: str) -> None:
    sometimes = _shelf_where(chil=_shelf(peanut=Frequency.SOMETIMES))
    usually = _shelf_where(chil=_shelf(peanut=Frequency.USUALLY))
    names = [name, "Soy Sauce"]

    assert audit.resolve_truth("peanut-free", "rec_x", names, _UNSURE, lookup=sometimes) == "fine"
    assert audit.resolve_truth("peanut-free", "rec_x", names, _UNSURE, lookup=usually) == "breaks"
    assert audit.resolve_truth("tree-nut-free", "rec_x", names, _UNSURE, lookup=usually) == "fine"


def test_a_crispy_chilli_oil_is_settled_by_its_own_shelf_not_by_the_soy_sauce_beside_it() -> None:
    peanut_oil = _shelf_where(chilli_oil=_shelf(peanut=Frequency.USUALLY))
    clean_oil = _shelf_where(chilli_oil=_shelf())

    assert audit.resolve_truth("peanut-free", "rec_x", _CHILLI_OIL_RECIPE, _UNSURE, lookup=peanut_oil) == "breaks"
    assert audit.resolve_truth("tree-nut-free", "rec_x", _CHILLI_OIL_RECIPE, _UNSURE, lookup=peanut_oil) == "fine"
    assert audit.resolve_truth("peanut-free", "rec_x", _CHILLI_OIL_RECIPE, _UNSURE, lookup=clean_oil) == "fine"


@pytest.mark.parametrize("name", ["Chilli Oil", "chilli oil", "Crispy Chilli Oil", "Chilli Crunch"])
@pytest.mark.parametrize("flag", ["tree-nut-free", "peanut-free"])
def test_a_recipe_is_never_fine_while_its_chilli_oil_is_unread(name: str, flag: str) -> None:
    def shelf(ingredient: str) -> IngredientVerdict:
        if "chil" in ingredient.casefold():
            return IngredientVerdict(ingredient=ingredient, status="not_found")
        return _shelf()

    truth = audit.resolve_truth(flag, "rec_x", [name, "Soy Sauce"], _UNSURE, lookup=shelf)

    assert truth is None


def test_a_plain_chilli_oil_the_shelf_reads_as_nut_free_is_fine_for_both_flags() -> None:
    names = ["Chilli Oil", "Soy Sauce"]

    for flag in audit.NUT_FLAGS:
        assert audit.resolve_truth(flag, "rec_x", names, _UNSURE, lookup=_all_safe) == "fine"
