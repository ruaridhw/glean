from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from glean.decisions import DECISION_MODEL
from glean.meal_plan.candidates import PantryItem, sample_corpus_candidates, urgent_pantry_uses
from glean.meal_plan.dietary_decisions import (
    DietaryDecision,
    DietaryDecisionStore,
    content_fingerprint,
    dietary_questions,
    question_hash,
)
from glean.meal_plan.eligibility import CookedMeal
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe

CURRENT_MODEL = f"{DECISION_MODEL}-20261014"


def _pantry(*names: str) -> list[PantryItem]:
    """Pantry items with no urgency information: every match counts as one, as before V4."""
    return [PantryItem(name=name) for name in names]


def test_pantry_matches_fill_the_sample_before_unrelated_recipes(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_bolognese", "Beef Bolognese", ["beef mince", "chopped tomatoes"], 30),
            ("rec_chilli", "Chilli Con Carne", ["beef mince", "kidney beans"], 40),
            ("rec_salmon", "Salmon Teriyaki", ["salmon fillet", "soy sauce"], 25),
            ("rec_risotto", "Mushroom Risotto", ["arborio rice", "mushrooms"], 35),
        ],
    )

    candidates = sample_corpus_candidates(
        corpus,
        pantry=_pantry("mince", "tinned tomatoes"),
        dietary_flags=[],
        max_total_time_mins=None,
        exclude_external_ids=[],
        rng=random.Random(0),
        sample_size=2,
    )

    assert {candidate.external_id for candidate in candidates} == {"rec_bolognese", "rec_chilli"}


def test_plural_pantry_names_match_singular_ingredients(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_mash", "Sausage and Mash", ["potato", "sausage"], 30),
            ("rec_salad", "Green Salad", ["lettuce"], 10),
        ],
    )

    candidates = sample_corpus_candidates(
        corpus,
        pantry=_pantry("potatoes"),
        dietary_flags=[],
        max_total_time_mins=None,
        exclude_external_ids=[],
        rng=random.Random(0),
        sample_size=1,
    )

    assert [candidate.external_id for candidate in candidates] == ["rec_mash"]


def test_tops_up_with_random_recipes_when_pantry_matches_run_out(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_bolognese", "Beef Bolognese", ["beef mince"], 30),
            ("rec_salmon", "Salmon Teriyaki", ["salmon fillet"], 25),
            ("rec_risotto", "Mushroom Risotto", ["arborio rice"], 35),
        ],
    )

    candidates = sample_corpus_candidates(
        corpus,
        pantry=_pantry("mince"),
        dietary_flags=[],
        max_total_time_mins=None,
        exclude_external_ids=[],
        rng=random.Random(0),
        sample_size=3,
    )

    assert candidates[0].external_id == "rec_bolognese"
    assert {candidate.external_id for candidate in candidates} == {"rec_bolognese", "rec_salmon", "rec_risotto"}


def test_excludes_planned_recipes_and_recipes_over_the_time_limit(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_planned", "Beef Bolognese", ["beef mince"], 30),
            ("rec_slow", "Slow Beef Stew", ["beef mince", "carrot"], 180),
            ("rec_untimed", "Beef Tacos", ["beef mince", "tortilla"], None),
            ("rec_quick", "Beef Stir Fry", ["beef mince", "noodles"], 20),
        ],
    )

    candidates = sample_corpus_candidates(
        corpus,
        pantry=_pantry("mince"),
        dietary_flags=[],
        max_total_time_mins=45,
        exclude_external_ids=["rec_planned"],
        rng=random.Random(0),
        sample_size=10,
    )

    assert {candidate.external_id for candidate in candidates} == {"rec_untimed", "rec_quick"}


def test_sampling_varies_with_the_random_source(tmp_path) -> None:
    corpus = _corpus(tmp_path, [(f"rec_{i}", f"Beef Dish {i}", ["beef mince", f"spice {i}"], 30) for i in range(40)])

    def sample(seed: int) -> list[str]:
        candidates = sample_corpus_candidates(
            corpus,
            pantry=_pantry("mince"),
            dietary_flags=[],
            max_total_time_mins=None,
            exclude_external_ids=[],
            rng=random.Random(seed),
            sample_size=5,
        )
        return [candidate.external_id for candidate in candidates]

    assert sample(1) == sample(1)
    assert sample(1) != sample(2)


def test_near_duplicate_recipes_are_offered_at_most_once(tmp_path) -> None:
    bake = ["penne", "cheddar cheese", "courgette", "tomato paste", "garlic"]
    corpus = _corpus(
        tmp_path,
        [
            ("rec_bake", "Cheese Veg-Packed Pasta Bake", bake, 30),
            ("rec_bake_3", "3 Cheese Veg-Packed Pasta Bake", [*bake, "mozzarella"], 30),
            ("rec_bake_ww", "3 Cheese Veg-Packed Wholewheat Pasta Bake", [*bake, "wholewheat penne"], 30),
            ("rec_curry", "Tomato Curry", ["tomato paste", "cumin", "rice"], 30),
        ],
    )

    candidates = _sample(corpus, pantry=["tomato paste"], dietary_flags=[])

    ids = {candidate.external_id for candidate in candidates}
    assert len(ids & {"rec_bake", "rec_bake_3", "rec_bake_ww"}) == 1
    assert "rec_curry" in ids


def test_flags_without_a_decision_question_leave_candidates_to_the_model(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_pasta", "Pasta Bake", ["penne", "cheese"], 30)])

    assert [c.external_id for c in _sample(corpus, pantry=[], dietary_flags=["Keto", "Paleo"])] == ["rec_pasta"]


def test_relaxed_recipes_fill_only_the_candidates_fresh_recipes_cannot(tmp_path) -> None:
    corpus, fresh_ids, relaxed_ids = _mixed_corpus(tmp_path)
    cooked = [_cooked_meal(f"rec_relaxed_{index}", f"Relaxed Dish {index}", days_ago=10) for index in range(10)]

    for seed in range(5):
        candidates = sample_corpus_candidates(
            corpus,
            pantry=_pantry("spice"),
            dietary_flags=[],
            max_total_time_mins=None,
            exclude_external_ids=[],
            rng=random.Random(seed),
            cooked=cooked,
            slots=7,
        )
        ids = [candidate.external_id for candidate in candidates]

        assert len(ids) == 25, f"seed {seed}: {len(ids)} candidates"
        assert set(ids[: len(fresh_ids)]) == fresh_ids, f"seed {seed}: relaxed recipe offered before a fresh one"
        assert set(ids[len(fresh_ids) :]) <= relaxed_ids, f"seed {seed}: {set(ids) - fresh_ids - relaxed_ids}"


def test_relaxed_recipes_fill_last_when_nothing_matches_the_pantry_either(tmp_path) -> None:
    corpus, fresh_ids, relaxed_ids = _mixed_corpus(tmp_path)
    cooked = [_cooked_meal(f"rec_relaxed_{index}", f"Relaxed Dish {index}", days_ago=10) for index in range(10)]

    for seed in range(5):
        candidates = sample_corpus_candidates(
            corpus,
            pantry=[],
            dietary_flags=[],
            max_total_time_mins=None,
            exclude_external_ids=[],
            rng=random.Random(seed),
            cooked=cooked,
            slots=7,
        )
        ids = [candidate.external_id for candidate in candidates]

        assert set(ids[: len(fresh_ids)]) == fresh_ids, f"seed {seed}: relaxed recipe offered before a fresh one"
        assert set(ids[len(fresh_ids) :]) <= relaxed_ids, f"seed {seed}: unexpected ids"


def _mixed_corpus(tmp_path) -> tuple[RecipeCorpusStore, set[str], set[str]]:
    """Twenty never-cooked recipes and ten cooked ten days ago: too few fresh ones for a seven-meal week."""
    fresh = [
        (f"rec_fresh_{index}", f"Fresh Dish {index}", ["spice", f"fresh thing {index}"], 30) for index in range(20)
    ]
    relaxed = [
        (f"rec_relaxed_{index}", f"Relaxed Dish {index}", ["spice", f"relaxed thing {index}"], 30)
        for index in range(10)
    ]
    return (
        _corpus(tmp_path, [*fresh, *relaxed]),
        {recipe[0] for recipe in fresh},
        {recipe[0] for recipe in relaxed},
    )


def _cooked_meal(recipe_id: str, title: str, *, days_ago: float) -> CookedMeal:
    return CookedMeal(recipe_id=recipe_id, title=title, cooked_at=datetime.now(UTC) - timedelta(days=days_ago))


def _sample(corpus: RecipeCorpusStore, *, pantry: list[str], dietary_flags: list[str]) -> list:
    return sample_corpus_candidates(
        corpus,
        pantry=_pantry(*pantry),
        dietary_flags=dietary_flags,
        max_total_time_mins=None,
        exclude_external_ids=[],
        rng=random.Random(0),
        sample_size=10,
    )


def _corpus(tmp_path, recipes: list[tuple[str, str, list[str], int | None]]) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for external_id, title, ingredients, total_time_mins in recipes:
        corpus.save(
            StoredRecipe(
                external_id=external_id,
                title=title,
                total_time_mins=total_time_mins,
                ingredients=[StoredIngredient(canonical_name=name, quantity=1, unit="each") for name in ingredients],
            )
        )
    return corpus


def test_recipes_cooked_in_the_last_six_weeks_are_not_offered(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_bolognese", "Beef Bolognese", ["beef mince"], 30),
            ("rec_chilli", "Chilli Con Carne", ["beef mince", "kidney beans"], 40),
            ("rec_tacos", "Beef Tacos", ["beef mince", "tortilla"], 20),
            ("rec_stir_fry", "Beef Stir Fry", ["beef mince", "noodles"], 20),
        ],
    )

    candidates = sample_corpus_candidates(
        corpus,
        pantry=_pantry("mince"),
        dietary_flags=[],
        max_total_time_mins=None,
        exclude_external_ids=[],
        rng=random.Random(0),
        cooked=[_cooked_meal("rec_chilli", "Chilli Con Carne", days_ago=10)],
        slots=1,
    )

    ids = {candidate.external_id for candidate in candidates}
    assert "rec_chilli" not in ids
    assert ids == {"rec_bolognese", "rec_tacos", "rec_stir_fry"}


def test_the_floor_relaxes_rather_than_leave_the_week_unfillable(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_bolognese", "Beef Bolognese", ["beef mince"], 30),
            ("rec_chilli", "Chilli Con Carne", ["beef mince", "kidney beans"], 40),
            ("rec_tacos", "Beef Tacos", ["beef mince", "tortilla"], 20),
        ],
    )

    candidates = sample_corpus_candidates(
        corpus,
        pantry=_pantry("mince"),
        dietary_flags=[],
        max_total_time_mins=None,
        exclude_external_ids=[],
        rng=random.Random(0),
        cooked=[_cooked_meal("rec_chilli", "Chilli Con Carne", days_ago=10)],
        slots=1,
    )

    assert {candidate.external_id for candidate in candidates} == {"rec_bolognese", "rec_chilli", "rec_tacos"}


def test_relaxing_the_floor_never_brings_back_a_recipe_a_hard_constraint_ruled_out(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_bolognese", "Beef Bolognese", ["beef mince"], 30),
            ("rec_planned", "Beef Pie", ["beef mince", "pastry"], 60),
            ("rec_chilli", "Chilli Con Carne", ["beef mince", "kidney beans"], 40),
        ],
    )

    candidates = sample_corpus_candidates(
        corpus,
        pantry=_pantry("mince"),
        dietary_flags=[],
        max_total_time_mins=45,
        exclude_external_ids=["rec_planned"],
        rng=random.Random(0),
        cooked=[
            _cooked_meal("rec_chilli", "Chilli Con Carne", days_ago=10),
            _cooked_meal("rec_planned", "Beef Pie", days_ago=10),
        ],
        slots=1,
    )

    assert {candidate.external_id for candidate in candidates} == {"rec_bolognese", "rec_chilli"}


def test_relaxed_recipes_fill_the_candidates_only_after_the_fresh_ones(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_bolognese", "Beef Bolognese", ["beef mince"], 30),
            ("rec_tacos", "Beef Tacos", ["beef mince", "tortilla"], 20),
            ("rec_chilli", "Chilli Con Carne", ["beef mince", "kidney beans"], 40),
        ],
    )

    candidates = sample_corpus_candidates(
        corpus,
        pantry=_pantry("mince"),
        dietary_flags=[],
        max_total_time_mins=None,
        exclude_external_ids=[],
        rng=random.Random(0),
        cooked=[_cooked_meal("rec_chilli", "Chilli Con Carne", days_ago=10)],
        slots=1,
        pool_size=2,
        sample_size=2,
    )

    assert {candidate.external_id for candidate in candidates} == {"rec_bolognese", "rec_tacos"}


# ── V4: use it before it goes off ────────────────────────────────────────────
#
# Seam: `sample_corpus_candidates`. The pantry slice now carries each item's
# urgency score and (when known) the whole days until it expires.


def test_a_pantry_match_counts_by_its_urgency_not_as_one(tmp_path) -> None:
    # Two fillers use two low-urgency items each, so counting matches flatly (2 > 1) would fill
    # the pool with both of them and leave the dish using the urgent coriander out of it.
    corpus = _corpus(
        tmp_path,
        [
            ("rec_herby", "Herby Chicken", ["coriander", "chicken"], 20),
            ("rec_pasta", "Tomato Pasta", ["penne", "tomato"], 20),
            ("rec_bake", "Tomato Bake", ["penne", "tomato", "cheese"], 20),
        ],
    )
    pantry = [
        PantryItem(name="coriander", urgency_score=120.0),
        PantryItem(name="penne", urgency_score=5.0),
        PantryItem(name="tomato", urgency_score=5.0),
    ]

    for seed in range(20):
        candidates = sample_corpus_candidates(
            corpus,
            pantry=pantry,
            dietary_flags=[],
            max_total_time_mins=None,
            exclude_external_ids=[],
            rng=random.Random(seed),
            sample_size=2,
            pool_size=2,
        )
        ids = [candidate.external_id for candidate in candidates]
        assert "rec_herby" in ids, f"seed {seed}: {ids}"
        assert len({"rec_pasta", "rec_bake"} & set(ids)) == 1, f"seed {seed}: {ids}"


def test_a_recipe_using_an_item_expiring_within_three_days_always_reaches_the_model(tmp_path) -> None:
    # Sixty recipes that all use the same well-stocked item, so the coriander dish loses every
    # sampling lottery: it ranks below the pool and only the random top-up could ever reach it.
    corpus = _corpus(
        tmp_path,
        [
            *[(f"rec_rice_{i}", f"Rice Dish {i}", ["rice", f"spice {i}"], 20) for i in range(60)],
            ("rec_coriander", "Coriander Chicken", ["chicken", "coriander"], 20),
        ],
    )
    pantry = [
        PantryItem(name="rice", urgency_score=200.0),
        PantryItem(name="coriander", urgency_score=110.0, expires_in_days=2),
    ]

    for seed in range(40):
        candidates = sample_corpus_candidates(
            corpus,
            pantry=pantry,
            dietary_flags=[],
            max_total_time_mins=None,
            exclude_external_ids=[],
            rng=random.Random(seed),
            sample_size=5,
        )
        assert "rec_coriander" in {candidate.external_id for candidate in candidates}, f"seed {seed}"


def test_a_pantry_item_expiring_beyond_three_days_is_not_guaranteed(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            *[(f"rec_rice_{i}", f"Rice Dish {i}", ["rice", f"spice {i}"], 20) for i in range(60)],
            ("rec_coriander", "Coriander Chicken", ["chicken", "coriander"], 20),
        ],
    )
    # The most urgent item of all, so a 3-day expiry would guarantee the dish; four days must not.
    pantry = [
        PantryItem(name="rice", urgency_score=200.0),
        PantryItem(name="coriander", urgency_score=220.0, expires_in_days=4),
    ]

    seeds = [
        {
            candidate.external_id
            for candidate in sample_corpus_candidates(
                corpus,
                pantry=pantry,
                dietary_flags=[],
                max_total_time_mins=None,
                exclude_external_ids=[],
                rng=random.Random(seed),
                sample_size=5,
            )
        }
        for seed in range(40)
    ]

    assert any("rec_coriander" not in ids for ids in seeds)


def test_guaranteed_inclusions_are_bounded_so_the_list_still_varies(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            *[(f"rec_herby_{i}", f"Herby Dish {i}", ["coriander", f"spice {i}"], 20) for i in range(8)],
            *[(f"rec_rice_{i}", f"Rice Dish {i}", ["rice", f"grain {i}"], 20) for i in range(20)],
        ],
    )
    pantry = [
        PantryItem(name="coriander", urgency_score=150.0, expires_in_days=1),
        PantryItem(name="rice", urgency_score=200.0),
    ]

    candidates = sample_corpus_candidates(
        corpus,
        pantry=pantry,
        dietary_flags=[],
        max_total_time_mins=None,
        exclude_external_ids=[],
        rng=random.Random(0),
        sample_size=5,
        pool_size=20,
        guarantee_max=3,
    )

    ids = [candidate.external_id for candidate in candidates]
    # Three of the eight herby dishes are forced in; the rice pool then fills the other two slots.
    assert len(ids) == 5
    assert all(recipe_id.startswith("rec_herby_") for recipe_id in ids[:3]), ids
    assert all(recipe_id.startswith("rec_rice_") for recipe_id in ids[3:]), ids


def test_an_urgent_fresh_recipe_is_offered_before_any_recently_cooked_one(tmp_path) -> None:
    # The floor gives way here (too few fresh recipes for the week), so relaxed recipes are in the
    # candidate list; the guaranteed urgent fresh one must still lead it.
    corpus = _corpus(
        tmp_path,
        [
            ("rec_herby", "Coriander Chicken", ["chicken", "coriander"], 20),
            *[(f"rec_fresh_{i}", f"Fresh Dish {i}", [f"fresh thing {i}"], 20) for i in range(3)],
            *[(f"rec_old_{i}", f"Old Dish {i}", ["rice", f"old thing {i}"], 20) for i in range(10)],
        ],
    )
    pantry = [PantryItem(name="coriander", urgency_score=150.0, expires_in_days=1)]
    cooked = [_cooked_meal(f"rec_old_{i}", f"Old Dish {i}", days_ago=10) for i in range(10)]

    for seed in range(10):
        candidates = sample_corpus_candidates(
            corpus,
            pantry=pantry,
            dietary_flags=[],
            max_total_time_mins=None,
            exclude_external_ids=[],
            rng=random.Random(seed),
            cooked=cooked,
            slots=5,
            sample_size=6,
        )
        ids = [candidate.external_id for candidate in candidates]
        fresh = {"rec_herby", *(f"rec_fresh_{i}" for i in range(3))}

        assert ids[0] == "rec_herby", f"seed {seed}: {ids}"
        assert set(ids[:4]) == fresh, f"seed {seed}: a recent repeat was offered before a fresh recipe"
        assert all(recipe_id.startswith("rec_old_") for recipe_id in ids[4:]), f"seed {seed}: {ids}"


def test_every_urgent_item_gets_a_guaranteed_recipe_before_one_gets_a_second(tmp_path) -> None:
    # Sixty rice dishes are all urgent and all outrank the one coriander dish, so a guarantee spent on
    # the highest urgency scores would spend itself entirely on rice and never offer the coriander.
    corpus = _corpus(
        tmp_path,
        [
            *[(f"rec_rice_{i}", f"Rice Dish {i}", ["rice", f"spice {i}"], 20) for i in range(60)],
            ("rec_coriander", "Herb Chicken", ["chicken", "coriander"], 20),
        ],
    )
    pantry = [
        PantryItem(name="rice", urgency_score=200.0, expires_in_days=1),
        PantryItem(name="coriander", urgency_score=110.0, expires_in_days=2),
    ]

    for seed in range(40):
        candidates = sample_corpus_candidates(
            corpus,
            pantry=pantry,
            dietary_flags=[],
            max_total_time_mins=None,
            exclude_external_ids=[],
            rng=random.Random(seed),
        )
        ids = [candidate.external_id for candidate in candidates]
        assert "rec_coriander" in ids, f"seed {seed}"
        assert len(ids) == 25


def test_a_recipe_covering_several_urgent_items_counts_once_against_the_bound(tmp_path) -> None:
    # One ten-herb recipe covers ten urgent items. Counting it once per item would spend the whole
    # guarantee allowance on a single recipe and leave the one coriander recipe unsampled.
    herbs = ["basil", "mint", "sage", "thyme", "oregano", "parsley", "rosemary", "chives", "dill", "tarragon"]
    corpus = _corpus(
        tmp_path,
        [
            *[(f"rec_rice_{i}", f"Rice Dish {i}", ["rice", f"spice {i}"], 20) for i in range(60)],
            ("rec_herbs", "Ten Herb Roast", herbs, 20),
            ("rec_coriander", "Herb Chicken", ["chicken", "coriander"], 20),
        ],
    )
    pantry = [
        *(PantryItem(name=herb, urgency_score=120.0, expires_in_days=1) for herb in herbs),
        PantryItem(name="coriander", urgency_score=110.0, expires_in_days=2),
        PantryItem(name="rice", urgency_score=2000.0),
    ]

    for seed in range(40):
        candidates = sample_corpus_candidates(
            corpus,
            pantry=pantry,
            dietary_flags=[],
            max_total_time_mins=None,
            exclude_external_ids=[],
            rng=random.Random(seed),
        )
        ids = [candidate.external_id for candidate in candidates]
        assert "rec_coriander" in ids, f"seed {seed}"
        assert len(ids) == 25


def test_a_diet_excluded_recipe_using_the_most_urgent_item_is_never_offered(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_nutty", "Coriander Cashew Salad", ["coriander", "cashew"], 20),
            ("rec_nutty_style", "Herby Chicken", ["coriander", "chicken"], 20),
        ],
    )
    # Both recipes need a current decision, or the dietary filter drops them for having none.
    _store_decisions(corpus, {("rec_nutty", "tree-nut-free"): 0.95, ("rec_nutty_style", "tree-nut-free"): 0.02})
    pantry = [PantryItem(name="coriander", urgency_score=150.0, expires_in_days=1)]

    for seed in range(40):
        candidates = sample_corpus_candidates(
            corpus,
            pantry=pantry,
            dietary_flags=["Tree-Nut-Free"],
            max_total_time_mins=None,
            exclude_external_ids=[],
            rng=random.Random(seed),
            sample_size=5,
        )
        ids = {candidate.external_id for candidate in candidates}
        assert "rec_nutty" not in ids, f"seed {seed}"
        assert "rec_nutty_style" in ids, f"seed {seed}"


def test_the_guarantee_cannot_revive_a_recipe_the_six_week_floor_dropped(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            *[(f"rec_rice_{i}", f"Rice Dish {i}", ["rice", f"spice {i}"], 20) for i in range(5)],
            ("rec_coriander", "Coriander Chicken", ["chicken", "coriander"], 20),
        ],
    )
    pantry = [PantryItem(name="coriander", urgency_score=150.0, expires_in_days=1)]

    for seed in range(20):
        candidates = sample_corpus_candidates(
            corpus,
            pantry=pantry,
            dietary_flags=[],
            max_total_time_mins=None,
            exclude_external_ids=[],
            rng=random.Random(seed),
            cooked=[_cooked_meal("rec_coriander", "Coriander Chicken", days_ago=10)],
            slots=1,
            now=datetime.now(UTC),
        )
        assert "rec_coriander" not in {candidate.external_id for candidate in candidates}, f"seed {seed}"


def _relaxed_week(tmp_path) -> tuple[RecipeCorpusStore, set[str], list[CookedMeal]]:
    """A valid seven-slot week the floor cannot fill: twenty fresh recipes and sixty-one cooked ten days ago."""
    fresh = [(f"rec_fresh_{index}", f"Fresh Dish {index}", [f"fresh thing {index}"], 20) for index in range(20)]
    relaxed = [(f"rec_rice_{index}", f"Rice Dish {index}", ["rice", f"spice {index}"], 20) for index in range(60)]
    relaxed.append(("rec_coriander", "Coriander Chicken", ["chicken", "coriander"], 20))
    corpus = _corpus(tmp_path, [*fresh, *relaxed])
    cooked = [_cooked_meal(recipe_id, title, days_ago=10) for recipe_id, title, _, _ in relaxed]
    return corpus, {recipe[0] for recipe in fresh}, cooked


def test_a_relaxed_recipe_covers_an_urgent_item_no_fresh_recipe_uses(tmp_path) -> None:
    # The floor relaxed, so these recipes are eligible (spec §6.2 step 2) and step 4 guarantees urgent
    # uses over what is eligible. Nothing fresh uses the coriander, so a relaxed slot must carry it.
    corpus, fresh_ids, cooked = _relaxed_week(tmp_path)
    pantry = [
        PantryItem(name="rice", urgency_score=200.0, expires_in_days=1),
        PantryItem(name="coriander", urgency_score=110.0, expires_in_days=2),
    ]

    for seed in range(40):
        candidates = sample_corpus_candidates(
            corpus,
            pantry=pantry,
            dietary_flags=[],
            max_total_time_mins=None,
            exclude_external_ids=[],
            rng=random.Random(seed),
            cooked=cooked,
            slots=7,
            now=datetime.now(UTC),
        )
        ids = [candidate.external_id for candidate in candidates]
        coriander = [candidate for candidate in candidates if candidate.external_id == "rec_coriander"]

        assert coriander, f"seed {seed}"
        assert set(ids[:20]) == fresh_ids, f"seed {seed}: a relaxed recipe was offered before a fresh one"
        # A repeat is still a fallback: the offer carries how long ago it was cooked.
        assert coriander[0].cooked_days_ago is not None


def test_a_fresh_recipe_takes_the_urgent_slot_before_a_relaxed_one(tmp_path) -> None:
    # The coriander has a fresh recipe and relaxed ones, and the rice only relaxed ones. Coverage must
    # spend the relaxed guarantee on the rice (nothing fresh can cover it), not on another coriander.
    fresh_coriander = ("rec_herby", "Coriander Chicken", ["chicken", "coriander"], 20)
    corpus = _corpus(
        tmp_path,
        [
            *[(f"rec_fresh_{index}", f"Fresh Dish {index}", [f"fresh thing {index}"], 20) for index in range(12)],
            fresh_coriander,
            *[(f"rec_rice_{index}", f"Rice Dish {index}", ["rice", f"spice {index}"], 20) for index in range(30)],
            *[
                (
                    f"rec_old_herby_{index}",
                    f"Old Coriander Chicken {index}",
                    ["chicken", "coriander", f"old spice {index}", f"old herb {index}"],
                    20,
                )
                for index in range(10)
            ],
        ],
    )
    cooked = [_cooked_meal(f"rec_rice_{index}", f"Rice Dish {index}", days_ago=10) for index in range(30)] + [
        _cooked_meal(f"rec_old_herby_{index}", f"Old Coriander Chicken {index}", days_ago=10) for index in range(10)
    ]
    pantry = [
        PantryItem(name="coriander", urgency_score=150.0, expires_in_days=1),
        PantryItem(name="rice", urgency_score=200.0, expires_in_days=2),
    ]

    for seed in range(10):
        candidates = sample_corpus_candidates(
            corpus,
            pantry=pantry,
            dietary_flags=[],
            max_total_time_mins=None,
            exclude_external_ids=[],
            rng=random.Random(seed),
            cooked=cooked,
            slots=7,
            now=datetime.now(UTC),
            guarantee_max=1,
        )
        # 13 fresh recipes, so the first relaxed slot is index 13: the guaranteed rice, not the old herby.
        ids = [candidate.external_id for candidate in candidates]
        assert ids[0] == "rec_herby", ids
        assert ids[13].startswith("rec_rice_"), f"seed {seed}: a relaxed coriander recipe took the slot"


def test_urgent_uses_come_from_the_ingredient_lines_not_a_shared_word(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_pepper", "Red Pepper Traybake", ["red pepper"], 20),
            ("rec_onion", "Red Onion Tart", ["red onion"], 20),
        ],
    )
    onion = PantryItem(name="red onion", urgency_score=120.0, expires_in_days=1)

    uses = urgent_pantry_uses(corpus, [onion], ["rec_pepper", "rec_onion"])

    assert set(uses) == {"rec_onion"}
    assert uses["rec_onion"] == (onion,)


def test_a_title_mention_alone_is_not_a_recipe_using_the_item(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_free", "Coriander-free dinner", ["rice"], 20)])
    coriander = PantryItem(name="coriander", urgency_score=120.0, expires_in_days=2)

    assert urgent_pantry_uses(corpus, [coriander], ["rec_free"]) == {}


def test_urgent_matching_respects_word_boundaries_and_extra_name_words(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_slime", "Dish A", ["slime"], 20),
            ("rec_boiled", "Dish B", ["boiled egg"], 20),
            ("rec_oil", "Dish C", ["oil"], 20),
            ("rec_plain_coriander", "Dish D", ["coriander"], 20),
        ],
    )
    ids = ["rec_slime", "rec_boiled", "rec_oil", "rec_plain_coriander"]
    pantry = [
        PantryItem(name="lime", urgency_score=120.0, expires_in_days=1),
        PantryItem(name="oil", urgency_score=120.0, expires_in_days=1),
        PantryItem(name="ground coriander", urgency_score=120.0, expires_in_days=1),
    ]

    uses = urgent_pantry_uses(corpus, pantry, ids)

    assert set(uses) == {"rec_oil"}
    assert [item.name for item in uses["rec_oil"]] == ["oil"]


def test_a_plural_pantry_name_still_matches_the_singular_ingredient(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_tart", "Onion Tart", ["red onion"], 20)])
    onions = PantryItem(name="red onions", urgency_score=120.0, expires_in_days=1)

    assert set(urgent_pantry_uses(corpus, [onions], ["rec_tart"])) == {"rec_tart"}


def test_a_recipe_that_only_names_an_urgent_item_in_its_title_is_not_guaranteed(tmp_path) -> None:
    # The title still ranks it into the search (discovery), but the rice dishes outrank it out of the
    # pool; only a guarantee could put it in the list, and a title is not evidence of the ingredient.
    corpus = _corpus(
        tmp_path,
        [
            *[(f"rec_rice_{i}", f"Rice Dish {i}", ["rice", f"spice {i}"], 20) for i in range(60)],
            ("rec_free", "Coriander-free dinner", ["barley"], 20),
        ],
    )
    pantry = [
        PantryItem(name="rice", urgency_score=200.0),
        PantryItem(name="coriander", urgency_score=120.0, expires_in_days=2),
    ]

    offered = [
        {
            candidate.external_id
            for candidate in sample_corpus_candidates(
                corpus,
                pantry=pantry,
                dietary_flags=[],
                max_total_time_mins=None,
                exclude_external_ids=[],
                rng=random.Random(seed),
                sample_size=5,
            )
        }
        for seed in range(40)
    ]

    assert all("rec_free" not in ids for ids in offered)


def _store_decisions(corpus: RecipeCorpusStore, probabilities: dict[tuple[str, str], float]) -> None:
    DietaryDecisionStore(corpus.store).save(
        [
            DietaryDecision(
                recipe_id=recipe_id,
                flag=flag,
                probability=probability,
                model=CURRENT_MODEL,
                content_hash=_fingerprint(corpus, recipe_id),
                criteria_hash=question_hash(dietary_questions()[flag]),
                computed_at=datetime(2026, 10, 16, tzinfo=UTC),
            )
            for (recipe_id, flag), probability in probabilities.items()
        ]
    )


def _fingerprint(corpus: RecipeCorpusStore, recipe_id: str) -> str:
    summary = next(s for s in corpus.search(per_page=1000)[0] if s.external_id == recipe_id)
    return content_fingerprint(summary.title, summary.ingredient_names)
