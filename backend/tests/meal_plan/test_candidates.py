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
            ("rec_slow", "Slow Beef Stew", ["beef mince"], 180),
            ("rec_untimed", "Beef Tacos", ["beef mince"], None),
            ("rec_quick", "Beef Stir Fry", ["beef mince"], 20),
        ],
    )

    candidates = sample_corpus_candidates(
        corpus,
        pantry_names=["mince"],
        max_total_time_mins=45,
        exclude_external_ids=["rec_planned"],
        rng=random.Random(0),
        sample_size=10,
    )

    assert {candidate.external_id for candidate in candidates} == {"rec_untimed", "rec_quick"}


def test_sampling_varies_with_the_random_source(tmp_path) -> None:
    corpus = _corpus(tmp_path, [(f"rec_{i}", f"Beef Dish {i}", ["beef mince"], 30) for i in range(40)])

    def sample(seed: int) -> list[str]:
        candidates = sample_corpus_candidates(
            corpus,
            pantry_names=["mince"],
            max_total_time_mins=None,
            exclude_external_ids=[],
            rng=random.Random(seed),
            sample_size=5,
        )
        return [candidate.external_id for candidate in candidates]

    assert sample(1) == sample(1)
    assert sample(1) != sample(2)


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
