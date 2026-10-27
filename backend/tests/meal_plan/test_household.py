"""Planning's reading of the household profile (V13b): dislikes, favourites, loved ingredients and cuisines."""

from __future__ import annotations

import logging

import pytest

from glean.meal_plan.candidates import mentions_item
from glean.meal_plan.household import (
    cuisine_for,
    disliked_recipe_ids,
    favourite_ids,
    loved_in,
    match_profile,
    profile_cuisines,
)
from glean.recipes.attributes import Cuisine


def mentions_disliked(ingredient_names: list[str], dislike: str) -> bool:
    """Whether one recipe with these ingredient names is one the dislike leaves out (the rule the tools apply)."""
    return disliked_recipe_ids([("rec", ingredient_names)], [dislike], log=False) == frozenset({"rec"})


# --- a dislike is a whole ingredient word, with plurals folded --------------------------------------------


@pytest.mark.parametrize(
    ("dislike", "ingredient"),
    [
        ("mushrooms", "mushroom"),
        ("mushroom", "chestnut mushrooms"),
        ("Mushrooms", "MUSHROOMS, sliced"),
        ("tomatoes", "cherry tomato"),
        ("chillies", "red chilli"),
        ("nut", "mixed nuts"),
        ("blue cheese", "crumbled blue cheese"),
    ],
)
def test_a_dislike_matches_the_ingredient_it_names(dislike: str, ingredient: str) -> None:
    assert mentions_disliked([ingredient], dislike)


@pytest.mark.parametrize(
    ("dislike", "ingredient"),
    [
        ("nut", "nutmeg"),
        ("nut", "coconut milk"),
        ("pea", "peanut butter"),
        ("ham", "graham crackers"),
        ("lime", "slime"),
        ("blue cheese", "cheese"),
        ("blue cheese", "blueberries and cheese"),
    ],
)
def test_a_dislike_never_matches_inside_another_word(dislike: str, ingredient: str) -> None:
    assert not mentions_disliked([ingredient], dislike)


@pytest.mark.parametrize(
    ("dislike", "ingredient"),
    [
        ("olives", "olive oil"),
        ("olive", "extra virgin olive oil"),
        ("pepper", "black pepper"),
        ("peppers", "freshly ground black pepper"),
        ("pepper", "white pepper"),
        ("pepper", "ground pepper"),
        ("pepper", "cracked black pepper"),
        ("pepper", "peppercorns"),
    ],
)
def test_a_staple_phrase_never_triggers_the_bare_dislike_of_its_modifier(dislike: str, ingredient: str) -> None:
    # A household that dislikes olives still cooks with olive oil; one that dislikes peppers still seasons.
    assert not mentions_disliked([ingredient], dislike)


@pytest.mark.parametrize(
    ("dislike", "ingredient"),
    [
        ("olive oil", "olive oil"),
        ("black pepper", "cracked black pepper"),
        ("olives", "olive oil and black olives"),
        ("pepper", "red pepper"),
        ("peppers", "black pepper, roasted peppers"),
        ("oil", "olive oil"),
    ],
)
def test_the_stop_list_only_ever_spares_the_staple_itself(dislike: str, ingredient: str) -> None:
    # A dislike that names the phrase, an ingredient that also names the disliked thing, or a dislike of the head
    # word still excludes: the list is small because a dislike may be an allergy.
    assert mentions_disliked([ingredient], dislike)


@pytest.mark.parametrize(
    ("dislike", "ingredient"),
    [
        ("ox", "ox cheek"),
        ("jalapeño", "sliced jalapeno"),
        ("jalapeno", "Jalapeños"),
        ("crème fraîche", "half-fat creme fraiche"),
        ("creme fraiche", "crème fraîche"),
    ],
)
def test_a_dislike_folds_accents_and_may_be_two_letters(dislike: str, ingredient: str) -> None:
    assert mentions_disliked([ingredient], dislike)


def test_a_two_letter_dislike_is_still_a_whole_word() -> None:
    assert not mentions_disliked(["oxtail"], "ox")
    assert not mentions_disliked(["boxed tomatoes"], "ox")


def test_pantry_matching_is_unchanged_by_the_dislike_rules() -> None:
    # The pantry's own matcher keeps its three-letter floor and its accents; only dislikes changed.
    assert not mentions_item("ox cheek", "ox")
    assert not mentions_item("sliced jalapeno", "jalapeño")


def test_a_blank_dislike_matches_nothing() -> None:
    assert not mentions_disliked(["mushrooms"], "  ")


def test_disliked_recipes_are_every_recipe_using_any_dislike_and_the_log_says_how_many_each_removed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    recipes = {
        "rec_mushroom": ("Mushroom risotto", ("arborio rice", "chestnut mushrooms")),
        "rec_nutmeg": ("Bechamel lasagne", ("lasagne sheets", "nutmeg")),
        "rec_both": ("Mushroom and olive pizza", ("mushroom", "olives")),
        "rec_clean": ("Fish pie", ("cod", "potatoes")),
    }

    with caplog.at_level(logging.INFO):
        excluded = disliked_recipe_ids(
            ((recipe_id, names) for recipe_id, (_title, names) in recipes.items()), ["mushrooms", "olive", "nut"]
        )

    assert excluded == frozenset({"rec_mushroom", "rec_both"})
    record = next(record for record in caplog.records if record.getMessage() == "disliked ingredients left out")
    assert record.removed_per_dislike == [2, 1, 0]  # type: ignore[attr-defined]
    assert record.removed == 2  # type: ignore[attr-defined]
    assert record.unmatchable == 0  # type: ignore[attr-defined]
    # Counts only: neither the household's words nor any recipe's text reaches the log.
    logged = repr(record.__dict__)
    assert "mushroom" not in logged.casefold()
    assert "risotto" not in logged.casefold()


def test_a_dislike_with_no_word_to_match_is_counted_in_the_log(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        excluded = disliked_recipe_ids([("rec_a", ("mushroom",))], ["x", "-", "mushroom"])

    assert excluded == frozenset({"rec_a"})
    record = next(record for record in caplog.records if record.getMessage() == "disliked ingredients left out")
    assert record.unmatchable == 2  # type: ignore[attr-defined]


def test_no_dislikes_exclude_nothing_and_log_nothing(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        assert disliked_recipe_ids([("rec_a", ("mushroom",))], []) == frozenset()
    assert not [record for record in caplog.records if record.getMessage() == "disliked ingredients left out"]


# --- favourites: the matched recipe, else the title exactly -----------------------------------------------


def test_a_favourite_is_its_matched_recipe_or_a_recipe_titled_the_same() -> None:
    recipes = [("rec_pie", "Fish pie"), ("rec_curry", "Thai Green  Curry!"), ("rec_other", "Green curry soup")]

    found = favourite_ids(recipes, [("Something else", "rec_pie"), ("thai green curry", None)])

    assert found == frozenset({"rec_pie", "rec_curry"})


def test_a_favourite_title_must_match_exactly_not_as_a_substring() -> None:
    assert favourite_ids([("rec_a", "Fish pie with peas")], [("Fish pie", None)]) == frozenset()


# --- loved ingredients ------------------------------------------------------------------------------------


def test_loved_ingredients_are_the_ones_the_recipe_uses_as_whole_words() -> None:
    assert loved_in(("fresh basil", "nutmeg", "garlic cloves"), ["basil", "nut", "garlic", "lemon"]) == (
        "basil",
        "garlic",
    )


# --- cuisines map to V5's enum through a small alias table ------------------------------------------------


@pytest.mark.parametrize(
    ("text", "cuisine"),
    [
        ("Italian", Cuisine.ITALIAN),
        ("italian food", Cuisine.ITALIAN),
        ("Middle Eastern", Cuisine.MIDDLE_EASTERN),
        ("middle_eastern", Cuisine.MIDDLE_EASTERN),
        ("Lebanese", Cuisine.MIDDLE_EASTERN),
        ("Sichuan", Cuisine.CHINESE),
        ("Moroccan cuisine", Cuisine.NORTH_AFRICAN),
        ("Malaysian", Cuisine.SOUTHEAST_ASIAN),
        ("Jamaican", Cuisine.CARIBBEAN),
        ("Peruvian", Cuisine.LATIN_AMERICAN),
        ("English", Cuisine.BRITISH),
    ],
)
def test_a_cuisine_string_maps_to_the_enum(text: str, cuisine: Cuisine) -> None:
    assert cuisine_for(text) is cuisine


@pytest.mark.parametrize("text", ["Asian", "spicy food", "fusion", "other", "unsure", ""])
def test_an_unknown_or_catch_all_cuisine_maps_to_nothing(text: str) -> None:
    assert cuisine_for(text) is None


def test_profile_cuisines_ignore_unknown_strings_and_count_them_in_the_log(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        liked, avoided = profile_cuisines(["Italian", "Asian", "Sicilian-ish"], ["Thai", "Thai food"])

    assert liked == frozenset({Cuisine.ITALIAN})
    assert avoided == frozenset({Cuisine.THAI})
    record = next(record for record in caplog.records if record.getMessage() == "profile cuisines this backend ignored")
    assert record.unknown_cuisines == 2  # type: ignore[attr-defined]
    assert "asian" not in repr(record.__dict__).casefold()


def test_a_cuisine_both_liked_and_avoided_is_avoided_only() -> None:
    liked, avoided = profile_cuisines(["Thai"], ["thai"])

    assert liked == frozenset()
    assert avoided == frozenset({Cuisine.THAI})


def test_match_profile_finds_every_set_the_tools_read_in_one_pass(caplog: pytest.LogCaptureFixture) -> None:
    recipes = [
        ("rec_mushroom", "Mushroom risotto", ("chestnut mushrooms", "olive oil")),
        ("rec_pie", "Fish pie", ("cod", "fresh basil")),
        ("rec_other", "Lamb stew", ("lamb", "olive oil")),
    ]

    with caplog.at_level(logging.INFO):
        matches = match_profile(
            recipes, disliked=["mushrooms", "olives"], favourites=[("fish pie", None)], loved=["basil"], log=False
        )

    assert matches.disliked_ids == frozenset({"rec_mushroom"})
    assert matches.favourite_ids == frozenset({"rec_pie"})
    assert matches.loved_ids == frozenset({"rec_pie"})
    # The offer already logged this session's dislike counts; a search's context does not log them again.
    assert not [record for record in caplog.records if record.getMessage() == "disliked ingredients left out"]
