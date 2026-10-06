from __future__ import annotations

import random

from glean.meal_plan.candidates import sample_corpus_candidates
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe


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
        pantry_names=["mince", "tinned tomatoes"],
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
        pantry_names=["potatoes"],
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
        pantry_names=["mince"],
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
        pantry_names=["mince"],
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
            pantry_names=["mince"],
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


def test_vegetarian_excludes_meat_and_fish_but_keeps_vegan_alternatives(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_chicken", "Chicken Curry", ["chicken thigh", "tomato"], 30),
            ("rec_fish_sauce", "Pad Thai", ["rice noodles", "fish sauce", "tomato"], 30),
            ("rec_vegan_mince", "Veggie Chilli", ["vegan mince", "tomato"], 30),
            ("rec_dal", "Tomato Dal", ["red lentils", "tomato"], 30),
        ],
    )

    candidates = _sample(corpus, pantry=["tomatoes"], dietary_flags=["Vegetarian"])

    assert {candidate.external_id for candidate in candidates} == {"rec_vegan_mince", "rec_dal"}


def test_vegan_also_excludes_dairy_eggs_and_honey_but_keeps_plant_milks(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_halloumi", "Halloumi Bake", ["halloumi", "tomato"], 30),
            ("rec_egg", "Shakshuka", ["eggs", "tomato"], 30),
            ("rec_honey", "Honey Roast Veg", ["honey", "carrot"], 30),
            ("rec_coconut", "Coconut Curry", ["coconut milk", "tomato"], 30),
        ],
    )

    candidates = _sample(corpus, pantry=["tomatoes"], dietary_flags=["vegan"])

    assert [candidate.external_id for candidate in candidates] == ["rec_coconut"]


def test_gluten_free_excludes_wheat_but_keeps_rice_noodles_and_cornflour(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_spaghetti", "Spaghetti Pomodoro", ["spaghetti", "tomato"], 30),
            ("rec_soy", "Stir Fry", ["soy sauce", "pepper"], 30),
            ("rec_rice_noodles", "Noodle Bowl", ["rice noodles", "cornflour", "pepper"], 30),
        ],
    )

    candidates = _sample(corpus, pantry=["pepper"], dietary_flags=["Gluten-Free"])

    assert [candidate.external_id for candidate in candidates] == ["rec_rice_noodles"]


def test_dairy_free_and_nut_free_exclusions(tmp_path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            ("rec_cheese", "Cheese Toastie", ["cheddar cheese", "bread"], 10),
            ("rec_satay", "Satay Skewers", ["peanut butter", "tofu"], 20),
            ("rec_oat", "Overnight Oats", ["oat milk", "banana"], 5),
        ],
    )

    assert [c.external_id for c in _sample(corpus, pantry=[], dietary_flags=["Dairy-Free", "Nut-Free"])] == ["rec_oat"]
    assert {c.external_id for c in _sample(corpus, pantry=[], dietary_flags=["Dairy-Free"])} == {"rec_satay", "rec_oat"}


def test_flags_without_ingredient_rules_leave_candidates_to_the_model(tmp_path) -> None:
    corpus = _corpus(tmp_path, [("rec_pasta", "Pasta Bake", ["penne", "cheese"], 30)])

    assert [c.external_id for c in _sample(corpus, pantry=[], dietary_flags=["Keto", "Paleo"])] == ["rec_pasta"]


def _sample(corpus: RecipeCorpusStore, *, pantry: list[str], dietary_flags: list[str]) -> list:
    return sample_corpus_candidates(
        corpus,
        pantry_names=pantry,
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
