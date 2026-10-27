"""The household profile as planning reads it (spec 6.4, V13b): what it excludes, what it scores, what a prompt sees.

The profile's four ingredient and cuisine lists are still plain strings (spec 6.4), so this module is where they
meet the corpus:

- **Disliked ingredients** are a hard constraint beside the dietary decisions: a recipe whose ingredient names use
  one, as a whole word with plurals folded (`candidates.mentions_item`, the same rule a pantry match uses), is never
  offered. "nut" does not hit "nutmeg" or "coconut". `disliked_recipe_ids` logs how many recipes each dislike left
  out, by position, and never the words.
- **Favourite meals** are the corpus recipe the interview matched, or else a recipe whose title is the same after
  normalising case, spacing and punctuation. Never a substring: "Fish pie" is not "Fish pie with peas".
- **Loved ingredients** are matched like dislikes, and **cuisines** go through `CUISINE_ALIASES` to V5's `Cuisine`
  enum. A cuisine string this table does not know is ignored and counted in the log.

The scorer weights for all of these are `tools.ScorerWeights`'; this module only decides which recipes they apply to.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from glean.meal_plan.candidates import mentions_item
from glean.observability import logger
from glean.recipes.attributes import Cuisine

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

_NON_WORD_RE = re.compile(r"[\W_]+")
# Words a household adds around a cuisine that do not change which one it is ("Thai food", "Italian cooking").
_CUISINE_FILLER = frozenset({"food", "cuisine", "cooking", "dishes", "style", "inspired"})

# A household's word for a cuisine, after `_normalised`, and V5's value for it. Small on purpose: the lists become
# enum sets once real answers show the vocabulary (spec 6.4). Each enum value is its own alias too. "Asian" is
# missing deliberately: it names five of the enum's values, so it cannot pick one.
CUISINE_ALIASES: dict[str, Cuisine] = {
    **{value.value.replace("_", " "): value for value in Cuisine if value not in {Cuisine.UNSURE, Cuisine.OTHER}},
    "english": Cuisine.BRITISH,
    "scottish": Cuisine.BRITISH,
    "welsh": Cuisine.BRITISH,
    "irish": Cuisine.BRITISH,
    "uk": Cuisine.BRITISH,
    "italy": Cuisine.ITALIAN,
    "sicilian": Cuisine.ITALIAN,
    "france": Cuisine.FRENCH,
    "spain": Cuisine.SPANISH,
    "tapas": Cuisine.SPANISH,
    "lebanese": Cuisine.MIDDLE_EASTERN,
    "turkish": Cuisine.MIDDLE_EASTERN,
    "persian": Cuisine.MIDDLE_EASTERN,
    "iranian": Cuisine.MIDDLE_EASTERN,
    "israeli": Cuisine.MIDDLE_EASTERN,
    "syrian": Cuisine.MIDDLE_EASTERN,
    "moroccan": Cuisine.NORTH_AFRICAN,
    "tunisian": Cuisine.NORTH_AFRICAN,
    "algerian": Cuisine.NORTH_AFRICAN,
    "egyptian": Cuisine.NORTH_AFRICAN,
    "south indian": Cuisine.INDIAN,
    "punjabi": Cuisine.INDIAN,
    "cantonese": Cuisine.CHINESE,
    "sichuan": Cuisine.CHINESE,
    "szechuan": Cuisine.CHINESE,
    "malaysian": Cuisine.SOUTHEAST_ASIAN,
    "indonesian": Cuisine.SOUTHEAST_ASIAN,
    "filipino": Cuisine.SOUTHEAST_ASIAN,
    "singaporean": Cuisine.SOUTHEAST_ASIAN,
    "tex mex": Cuisine.MEXICAN,
    "jamaican": Cuisine.CARIBBEAN,
    "trinidadian": Cuisine.CARIBBEAN,
    "usa": Cuisine.AMERICAN,
    "us": Cuisine.AMERICAN,
    "southern": Cuisine.AMERICAN,
    "brazilian": Cuisine.LATIN_AMERICAN,
    "peruvian": Cuisine.LATIN_AMERICAN,
    "argentinian": Cuisine.LATIN_AMERICAN,
    "colombian": Cuisine.LATIN_AMERICAN,
    "south american": Cuisine.LATIN_AMERICAN,
}


def mentions_disliked(ingredient_names: Iterable[str], dislike: str) -> bool:
    """Whether any ingredient name uses *dislike* as whole words, plurals folded, never inside another word."""
    return bool(dislike.strip()) and any(mentions_item(name, dislike) for name in ingredient_names)


def disliked_recipe_ids(recipes: Iterable[tuple[str, Sequence[str]]], dislikes: Sequence[str]) -> frozenset[str]:
    """The recipes, given as (id, ingredient names), that use any of the household's disliked ingredients.

    Logs how many recipes each dislike removed, in the profile's order, and how many were removed in all: counts
    only, so neither the household's words nor a recipe's text is ever logged.
    """
    wanted = [dislike for dislike in dislikes if dislike.strip()]
    if not wanted:
        return frozenset()
    removed_per_dislike = [0] * len(wanted)
    excluded: set[str] = set()
    for recipe_id, names in recipes:
        hits = [index for index, dislike in enumerate(wanted) if mentions_disliked(names, dislike)]
        for index in hits:
            removed_per_dislike[index] += 1
        if hits:
            excluded.add(recipe_id)
    logger.info(
        "disliked ingredients left out",
        extra={"dislikes": len(wanted), "removed_per_dislike": removed_per_dislike, "removed": len(excluded)},
    )
    return frozenset(excluded)


def favourite_ids(recipes: Iterable[tuple[str, str]], favourites: Iterable[tuple[str, str | None]]) -> frozenset[str]:
    """The recipes, given as (id, title), that are one of the household's favourites, given as (text, recipe id).

    A favourite the interview matched is that recipe. One it did not is any recipe whose normalised title is the
    favourite's normalised text exactly.
    """
    matched_ids: set[str] = set()
    titles: set[str] = set()
    for text, recipe_id in favourites:
        if recipe_id:
            matched_ids.add(recipe_id)
        elif normalised := _normalised(text):
            titles.add(normalised)
    return frozenset(
        recipe_id for recipe_id, title in recipes if recipe_id in matched_ids or _normalised(title) in titles
    )


def loved_in(ingredient_names: Sequence[str], loved: Sequence[str]) -> tuple[str, ...]:
    """The household's loved ingredients this recipe uses, in the profile's order (the scorer's +1 reads them)."""
    return tuple(item for item in loved if mentions_disliked(ingredient_names, item))


def cuisine_for(text: str) -> Cuisine | None:
    """V5's cuisine for a household's word for one, or None when the alias table does not know it."""
    words = [word for word in _normalised(text).split() if word not in _CUISINE_FILLER]
    return CUISINE_ALIASES.get(" ".join(words))


def profile_cuisines(liked: Sequence[str], avoided: Sequence[str]) -> tuple[frozenset[Cuisine], frozenset[Cuisine]]:
    """The liked and avoided cuisines as V5's enum. One named both ways is avoided only: the cautious reading.

    Strings the alias table does not know are ignored, and how many were is logged (never the strings).
    """
    mapped_liked = [cuisine_for(text) for text in liked]
    mapped_avoided = [cuisine_for(text) for text in avoided]
    unknown = sum(1 for cuisine in (*mapped_liked, *mapped_avoided) if cuisine is None)
    if unknown:
        logger.info("profile cuisines this backend ignored", extra={"unknown_cuisines": unknown})
    avoided_set = frozenset(cuisine for cuisine in mapped_avoided if cuisine is not None)
    liked_set = frozenset(cuisine for cuisine in mapped_liked if cuisine is not None) - avoided_set
    return liked_set, avoided_set


def _normalised(text: str) -> str:
    """Lower case, punctuation as spaces, spaces collapsed: "Thai Green  Curry!" is "thai green curry"."""
    return " ".join(_NON_WORD_RE.sub(" ", text.casefold()).split())
