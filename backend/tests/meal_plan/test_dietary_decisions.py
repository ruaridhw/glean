"""dietary decisions in corpus candidate selection (#125).

Seams: `sample_corpus_candidates` (the dietary-filtering step) and the decisions
stored beside the corpus. Decisions are placed through the stored-decision store,
the same blob the producer writes.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import httpx
import pytest

from glean.decisions import DECISION_MODEL, DEFAULT_MODEL, DecisionModel
from glean.meal_plan.candidates import sample_corpus_candidates
from glean.meal_plan.dietary_decisions import (
    CALIBRATED_DIETARY,
    DIETARY_DECISIONS_KEY,
    DIETARY_FLAGS,
    PREFERENCE_THRESHOLD,
    THRESHOLDS,
    TREE_NUT_FREE,
    DietaryCalibration,
    DietaryDecision,
    DietaryDecisions,
    DietaryDecisionStore,
    UncalibratedModelError,
    content_fingerprint,
    dietary_questions,
    question_hash,
)
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe

if TYPE_CHECKING:
    from glean.recipes.search_index import RecipeSummary

CURRENT_MODEL = f"{DECISION_MODEL}-20261014"
# A free route's request id and the identity it answers under differ, as observed in a pilot.
CANDIDATE = DecisionModel("baseten/mammoth-1:free", served=("baseten/mammoth-1",))
CANDIDATE_SERVED = "baseten/mammoth-1-20261021"


def test_a_recipe_a_stored_decision_flags_is_excluded_though_its_ingredients_look_harmless(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_pesto", "Pesto Pasta", ["spaghetti", "basil pesto"]),
            ("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"]),
        ],
    )
    _store_decisions(corpus, {("rec_pesto", "tree-nut-free"): 0.9, ("rec_tomato", "tree-nut-free"): 0.02})

    assert _ids(corpus, ["Tree-Nut-Free"]) == {"rec_tomato"}


def test_tree_nut_and_peanut_decisions_are_independent(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_satay", "Satay Noodles", ["noodles", "satay sauce"])])
    _store_decisions(corpus, {("rec_satay", "tree-nut-free"): 0.02, ("rec_satay", "peanut-free"): 0.99})

    assert _ids(corpus, ["tree-nut-free"]) == {"rec_satay"}
    assert _ids(corpus, ["peanut-free"]) == set()


@pytest.mark.parametrize("legacy", ["nut-free", "Nut-Free", " nut-free "])
@pytest.mark.parametrize(("tree_nut", "peanut"), [(0.99, 0.02), (0.02, 0.99), (0.99, 0.99)])
def test_a_legacy_nut_free_flag_from_an_older_app_excludes_a_recipe_that_breaks_either_new_flag(
    tmp_path, legacy: str, tree_nut: float, peanut: float
) -> None:
    corpus = _corpus(tmp_path, [("rec_nutty", "Nutty Bowl", ["rice", "nuts"])])
    _store_decisions(corpus, {("rec_nutty", "tree-nut-free"): tree_nut, ("rec_nutty", "peanut-free"): peanut})

    assert _ids(corpus, [legacy]) == set()


def test_a_legacy_nut_free_flag_offers_a_recipe_that_is_clear_of_both(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_rice", "Plain Rice", ["rice"])])
    _store_decisions(corpus, {("rec_rice", "tree-nut-free"): 0.02, ("rec_rice", "peanut-free"): 0.02})

    assert _ids(corpus, ["nut-free"]) == {"rec_rice"}


@pytest.mark.parametrize("answered", ["tree-nut-free", "peanut-free"])
def test_a_legacy_nut_free_flag_excludes_a_recipe_missing_either_decision(tmp_path, answered: str) -> None:
    corpus = _corpus(tmp_path, [("rec_rice", "Plain Rice", ["rice"])])
    _store_decisions(corpus, {("rec_rice", answered): 0.02})

    assert _ids(corpus, ["nut-free"]) == set()


def test_a_decision_stored_under_the_old_nut_free_flag_speaks_for_neither_new_flag(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_rice", "Plain Rice", ["rice"])])
    DietaryDecisionStore(corpus.store).save(
        [
            DietaryDecision(
                recipe_id="rec_rice",
                flag="nut-free",
                probability=0.01,
                model=CURRENT_MODEL,
                content_hash=_hash(corpus, "rec_rice"),
                criteria_hash="0" * 64,
                computed_at=datetime(2026, 10, 15, tzinfo=UTC),
            )
        ]
    )

    assert _ids(corpus, ["tree-nut-free"]) == set()
    assert _ids(corpus, ["peanut-free"]) == set()


@pytest.mark.parametrize("flag", DIETARY_FLAGS)
def test_a_stored_decision_alone_decides_so_a_low_probability_keeps_a_recipe_naming_a_forbidden_food(
    tmp_path, flag: str
) -> None:
    corpus = _corpus(tmp_path, [("rec_mixed", "Everything Bowl", ["chicken", "cheese", "peanut", "bread"])])
    _store_decisions(corpus, {("rec_mixed", flag): 0.0})

    assert _ids(corpus, [flag]) == {"rec_mixed"}


@pytest.mark.parametrize("flag", DIETARY_FLAGS)
def test_every_flag_excludes_a_recipe_with_no_stored_decision(tmp_path, flag: str) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_decided", "Tomato Pasta", ["spaghetti", "tomato"]),
            ("rec_new", "Courgette Pasta", ["spaghetti", "courgette"]),
        ],
    )
    _store_decisions(corpus, {("rec_decided", flag): 0.01})

    assert _ids(corpus, [flag]) == {"rec_decided"}


@pytest.mark.parametrize("flag", DIETARY_FLAGS)
def test_every_flag_excludes_everything_when_no_decisions_are_stored(tmp_path, flag: str) -> None:
    corpus = _corpus(tmp_path, [("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])])

    assert _ids(corpus, [flag]) == set()


@pytest.mark.parametrize("flag", DIETARY_FLAGS)
def test_every_flag_excludes_a_recipe_judged_under_an_older_model(tmp_path, flag: str) -> None:
    corpus = _corpus(tmp_path, [("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])])
    _store_decisions(corpus, {("rec_tomato", flag): 0.01}, model="typesafe/jev-1.13-20260917")

    assert _ids(corpus, [flag]) == set()


@pytest.mark.parametrize("flag", DIETARY_FLAGS)
def test_a_decision_computed_under_other_criteria_text_is_treated_as_missing(tmp_path, flag: str) -> None:
    corpus = _corpus(tmp_path, [("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])])
    question = dietary_questions()[flag]
    reworded = question.model_copy(update={"instructions": question.instructions + " Tahini counts."})
    _store_decisions(corpus, {("rec_tomato", flag): 0.01}, criteria_hash=question_hash(reworded))

    assert _ids(corpus, [flag]) == set()


def test_the_criteria_hash_changes_with_either_criterion_or_the_instructions() -> None:
    question = dietary_questions()["vegetarian"]
    criteria = question.criteria

    variants = [
        question.model_copy(update={"instructions": question.instructions + " "}),
        question.model_copy(update={"criteria": criteria.model_copy(update={"true": criteria.true + " "})}),
        question.model_copy(update={"criteria": criteria.model_copy(update={"false": criteria.false + " "})}),
    ]

    assert len({question_hash(question), *(question_hash(variant) for variant in variants)}) == 4


@pytest.mark.parametrize("flag", DIETARY_FLAGS)
def test_every_flag_excludes_a_recipe_whose_stored_decision_is_unreadable(tmp_path, flag: str) -> None:
    corpus = _corpus(tmp_path, [("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])])
    corpus.store.write(DIETARY_DECISIONS_KEY, '{"recipe_id": "rec_tomato", "flag": "nut-fr\n')

    assert _ids(corpus, [flag]) == set()


def test_flags_the_decision_model_isnt_asked_about_leave_candidates_alone(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_pasta", "Pasta Bake", ["penne", "cheese"])])

    assert _ids(corpus, ["Keto", "Paleo"]) == {"rec_pasta"}


def test_tree_nut_decisions_do_not_leak_into_other_flags(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_pesto", "Pesto Pasta", ["spaghetti", "basil pesto"])])
    _store_decisions(corpus, {("rec_pesto", "tree-nut-free"): 0.9, ("rec_pesto", "vegetarian"): 0.0})

    assert _ids(corpus, ["vegetarian"]) == {"rec_pesto"}


@pytest.mark.parametrize("allergy", ["tree-nut-free", "peanut-free"])
def test_the_nut_allergy_flags_are_stricter_than_the_preference_flags(tmp_path, allergy: str) -> None:
    corpus = _corpus(tmp_path, [("rec_maybe", "Mystery Stew", ["tomato", "sauce"])])
    # A probability high enough to worry about for an allergy, yet below "probably" for a preference.
    _store_decisions(corpus, {("rec_maybe", flag): 0.3 for flag in DIETARY_FLAGS})

    assert _ids(corpus, [allergy]) == set()
    for flag in ("vegetarian", "vegan", "dairy-free", "gluten-free"):
        assert _ids(corpus, [flag]) == {"rec_maybe"}


@pytest.mark.parametrize("flag", [*THRESHOLDS, "vegan"])
def test_a_probability_at_the_threshold_excludes(tmp_path, flag: str) -> None:
    corpus = _corpus(tmp_path, [("rec_edge", "Edge Stew", ["tomato", "sauce"])])
    _store_decisions(corpus, {("rec_edge", flag): THRESHOLDS.get(flag, PREFERENCE_THRESHOLD)})

    assert _ids(corpus, [flag]) == set()


def test_choosing_candidates_makes_no_network_call(tmp_path, monkeypatch) -> None:
    corpus = _corpus(tmp_path, [("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])])
    _store_decisions(corpus, {("rec_tomato", flag): 0.0 for flag in DIETARY_FLAGS})

    def refuse(*_args, **_kwargs):
        raise AssertionError("Generate must not call the decision model")

    monkeypatch.setattr(httpx.Client, "send", refuse)

    assert _ids(corpus, ["tree-nut-free", "peanut-free", "vegetarian"]) == {"rec_tomato"}


def test_a_calibration_reads_a_decision_under_the_identity_it_names(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_curry", "Korma", ["curry paste"])])
    decision = _decision(corpus, "rec_curry", "tree-nut-free", 0.02, model=CANDIDATE_SERVED)

    decisions = DietaryDecisions([decision], calibration=_calibration(CANDIDATE))

    assert not decisions.excludes(_summary(corpus, "rec_curry"), "tree-nut-free")


def test_a_calibration_ignores_a_decision_from_any_other_identity(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_curry", "Korma", ["curry paste"])])
    decision = _decision(corpus, "rec_curry", "tree-nut-free", 0.02, model=CURRENT_MODEL)

    decisions = DietaryDecisions([decision], calibration=_calibration(CANDIDATE))

    assert decisions.excludes(_summary(corpus, "rec_curry"), "tree-nut-free")


def test_the_calibrations_own_thresholds_decide_the_exclusion(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_curry", "Korma", ["curry paste"])])
    decision = _decision(corpus, "rec_curry", "tree-nut-free", 0.4, model=CANDIDATE_SERVED)
    summary = _summary(corpus, "rec_curry")

    permissive = DietaryDecisions([decision], calibration=_calibration(CANDIDATE, default_threshold=0.5))
    strict = DietaryDecisions([decision], calibration=_calibration(CANDIDATE, default_threshold=0.3))

    assert not permissive.excludes(summary, "tree-nut-free")
    assert strict.excludes(summary, "tree-nut-free")


@pytest.mark.parametrize("cutoff", [float("nan"), float("inf"), 0.0, -0.1, 1.0, 1.1])
def test_a_calibration_rejects_a_cutoff_outside_the_open_unit_interval(cutoff: float) -> None:
    with pytest.raises(ValueError, match="cutoff"):
        _calibration(DEFAULT_MODEL, thresholds={TREE_NUT_FREE: cutoff})

    with pytest.raises(ValueError, match="cutoff"):
        _calibration(DEFAULT_MODEL, default_threshold=cutoff)


@pytest.mark.parametrize("evidence", ["", "   \n"])
def test_a_calibration_needs_provenance_for_its_cutoffs(evidence: str) -> None:
    with pytest.raises(ValueError, match="evidence"):
        DietaryCalibration(model=DEFAULT_MODEL, thresholds={}, default_threshold=0.5, evidence=evidence)


def test_a_calibration_rejects_a_threshold_for_a_flag_the_model_is_not_asked_about() -> None:
    with pytest.raises(ValueError, match="keto"):
        _calibration(DEFAULT_MODEL, thresholds={"keto": 0.3})


def test_a_calibration_records_a_served_identity_only_under_the_model_it_covers() -> None:
    assert CALIBRATED_DIETARY.served_identity(CURRENT_MODEL) == CURRENT_MODEL

    with pytest.raises(UncalibratedModelError):
        CALIBRATED_DIETARY.served_identity(CANDIDATE_SERVED)


def test_a_calibration_owns_an_immutable_copy_of_the_cutoffs_it_was_given() -> None:
    cutoffs = {TREE_NUT_FREE: 0.3}
    calibration = _calibration(DEFAULT_MODEL, thresholds=cutoffs)

    cutoffs[TREE_NUT_FREE] = 0.9

    assert calibration.threshold_for(TREE_NUT_FREE) == 0.3
    with pytest.raises(TypeError):
        calibration.thresholds[TREE_NUT_FREE] = 0.9


def _calibration(
    model: DecisionModel,
    *,
    thresholds: dict[str, float] | None = None,
    default_threshold: float = 0.5,
) -> DietaryCalibration:
    return DietaryCalibration(
        model=model,
        thresholds={} if thresholds is None else thresholds,
        default_threshold=default_threshold,
        evidence="Observed responses on neutral samples only: a reference, not a calibration.",
    )


def _decision(
    corpus: RecipeCorpusStore, recipe_id: str, flag: str, probability: float, *, model: str
) -> DietaryDecision:
    return DietaryDecision(
        recipe_id=recipe_id,
        flag=flag,
        probability=probability,
        model=model,
        content_hash=_hash(corpus, recipe_id),
        criteria_hash=question_hash(dietary_questions()[flag]),
        computed_at=datetime(2026, 10, 15, tzinfo=UTC),
    )


@pytest.mark.parametrize("stale_hash", ["f" * 64, "0" * 64])
@pytest.mark.parametrize("stale_computed_last", [True, False])
def test_a_stale_criteria_answer_can_never_shadow_the_current_one(
    tmp_path, stale_hash: str, stale_computed_last: bool
) -> None:
    corpus = _corpus(tmp_path, [("rec_lentil", "Lentil Soup", ["lentils", "vegetable stock"])])
    current_hash = question_hash(dietary_questions()[TREE_NUT_FREE])
    assert current_hash not in {stale_hash, "0" * 64}
    stale_at = datetime(2026, 10, 20, tzinfo=UTC) if stale_computed_last else datetime(2026, 10, 1, tzinfo=UTC)
    current_at = datetime(2026, 10, 1, tzinfo=UTC) if stale_computed_last else datetime(2026, 10, 20, tzinfo=UTC)
    DietaryDecisionStore(corpus.store).save(
        [
            DietaryDecision(
                recipe_id="rec_lentil",
                flag=TREE_NUT_FREE,
                probability=0.9,
                model=CURRENT_MODEL,
                content_hash=_hash(corpus, "rec_lentil"),
                criteria_hash=stale_hash,
                computed_at=stale_at,
            ),
            DietaryDecision(
                recipe_id="rec_lentil",
                flag=TREE_NUT_FREE,
                probability=0.02,
                model=CURRENT_MODEL,
                content_hash=_hash(corpus, "rec_lentil"),
                criteria_hash=current_hash,
                computed_at=current_at,
            ),
        ]
    )

    assert _ids(corpus, [TREE_NUT_FREE]) == {"rec_lentil"}


def _ids(corpus: RecipeCorpusStore, flags: list[str]) -> set[str]:
    candidates = sample_corpus_candidates(
        corpus,
        pantry=[],
        dietary_flags=flags,
        max_total_time_mins=None,
        exclude_external_ids=[],
        rng=random.Random(0),
        sample_size=50,
    )
    return {candidate.external_id for candidate in candidates}


def _store_decisions(
    corpus: RecipeCorpusStore,
    probabilities: dict[tuple[str, str], float],
    *,
    model: str = CURRENT_MODEL,
    criteria_hash: str | None = None,
) -> None:
    DietaryDecisionStore(corpus.store).save(
        [
            DietaryDecision(
                recipe_id=recipe_id,
                flag=flag,
                probability=probability,
                model=model,
                content_hash=_hash(corpus, recipe_id),
                criteria_hash=criteria_hash or question_hash(dietary_questions()[flag]),
                computed_at=datetime(2026, 10, 15, tzinfo=UTC),
            )
            for (recipe_id, flag), probability in probabilities.items()
        ]
    )


def _summary(corpus: RecipeCorpusStore, recipe_id: str) -> RecipeSummary:
    return next(s for s in corpus.search(per_page=1000)[0] if s.external_id == recipe_id)


def _hash(corpus: RecipeCorpusStore, recipe_id: str) -> str:
    summary = _summary(corpus, recipe_id)
    return content_fingerprint(summary.title, summary.ingredient_names)


def _corpus(tmp_path, recipes: list[tuple[str, str, list[str]]]) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for external_id, title, ingredients in recipes:
        corpus.save(
            StoredRecipe(
                external_id=external_id,
                title=title,
                ingredients=[StoredIngredient(canonical_name=name, quantity=1, unit="each") for name in ingredients],
            )
        )
    return corpus


@pytest.mark.parametrize("uncovered_computed_last", [True, False])
def test_an_answer_from_a_model_the_calibration_does_not_cover_never_shadows_a_covered_one(
    tmp_path, uncovered_computed_last: bool
) -> None:
    corpus = _corpus(tmp_path, [("rec_curry", "Korma", ["curry paste"])])
    covered = _decision(corpus, "rec_curry", TREE_NUT_FREE, 0.02, model=CURRENT_MODEL)
    uncovered = _decision(corpus, "rec_curry", TREE_NUT_FREE, 0.02, model=CANDIDATE_SERVED).model_copy(
        update={"computed_at": covered.computed_at + timedelta(days=1 if uncovered_computed_last else -1)}
    )

    decisions = DietaryDecisions([uncovered, covered], calibration=CALIBRATED_DIETARY)

    assert not decisions.excludes(_summary(corpus, "rec_curry"), TREE_NUT_FREE)
