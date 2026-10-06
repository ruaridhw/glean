"""Choose which corpus recipes to offer the meal-plan model.

The model never sees the whole corpus. Recipes are ranked by how many pantry
items they use (via the corpus search index), a random sample of the best
matches becomes the candidate list, and random other recipes top it up when the
pantry matches too few. Randomness keeps repeated Generate taps varied.

Dietary flags are applied here, before sampling, because the corpus carries no
dietary metadata of its own: each rule excludes recipes with an ingredient
naming a forbidden food, unless that ingredient also carries a qualifier
that makes it safe ("vegan mince", "coconut milk", "rice noodles"). Flags without
an ingredient-level rule (Keto, Paleo) are left to the model.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import random
    from collections.abc import Collection, Sequence

    from glean.recipes.corpus import RecipeCorpusStore
    from glean.recipes.search_index import RecipeSummary

SAMPLE_SIZE = 25
PANTRY_POOL_SIZE = 60

_EVERYTHING = 1_000_000
_TOKEN_RE = re.compile(r"\w+")
_MIN_TOKEN_LENGTH = 3


def _words(*words: str) -> re.Pattern[str]:
    # Whole words, optionally plural: "egg" matches "eggs" but not "eggplant".
    return re.compile(r"\b(?:" + "|".join(re.escape(word) for word in words) + r")(?:s|es)?\b")


_PLANT_BASED = _words("vegan", "vegetarian", "veggie", "plant", "meat free", "meat-free", "meatless")
_MEAT_AND_FISH = (
    _words(
        "chicken",
        "beef",
        "pork",
        "lamb",
        "mince",
        "meat",
        "meatball",
        "steak",
        "bacon",
        "lardon",
        "chorizo",
        "nduja",
        "ham",
        "salami",
        "pancetta",
        "prosciutto",
        "sausage",
        "turkey",
        "duck",
        "venison",
        "gelatine",
        "lard",
        "suet",
        "fish",
        "salmon",
        "cod",
        "haddock",
        "basa",
        "tuna",
        "mackerel",
        "anchovy",
        "anchovies",
        "prawn",
        "shrimp",
        "crab",
        "mussel",
        "squid",
        "pollock",
        "hake",
        "sea bass",
        "seabass",
        "bream",
        "trout",
        "sardine",
        "plaice",
        "monkfish",
        "tilapia",
        "kipper",
        "lobster",
        "scallop",
        "clam",
        "calamari",
        "oyster",
        "worcestershire",
    ),
    _PLANT_BASED,
)
_DAIRY = (
    _words(
        "cheese",
        "cheddar",
        "mozzarella",
        "parmesan",
        "feta",
        "halloumi",
        "paneer",
        "ricotta",
        "mascarpone",
        "butter",
        "ghee",
        "milk",
        "cream",
        "creme fraiche",
        "crème fraîche",
        "yoghurt",
        "yogurt",
    ),
    _words(
        "vegan",
        "plant",
        "dairy free",
        "dairy-free",
        "coconut",
        "oat",
        "almond",
        "soy",
        "soya",
        "peanut",
        "cashew",
        "nut",
        "cocoa",
    ),
)
_EGGS_AND_HONEY = (_words("egg", "honey", "mayonnaise", "mayo"), _PLANT_BASED)
_GLUTEN = (
    _words(
        "wheat",
        "flour",
        "bread",
        "breadcrumb",
        "panko",
        "pasta",
        "spaghetti",
        "linguine",
        "tagliatelle",
        "penne",
        "rigatoni",
        "tortiglioni",
        "ditali",
        "orzo",
        "gnocchi",
        "couscous",
        "bulgur",
        "noodle",
        "naan",
        "ciabatta",
        "brioche",
        "sourdough",
        "flatbread",
        "pitta",
        "pita",
        "tortilla",
        "wrap",
        "bun",
        "pastry",
        "crouton",
        "barley",
        "rye",
        "beer",
        "soy sauce",
        "teriyaki",
        "hoisin",
        "seitan",
        "kecap manis",
        "ketjap manis",
    ),
    _words(
        "gluten free",
        "gluten-free",
        "rice",
        "corn",
        "cornflour",
        "gram",
        "buckwheat",
        "tapioca",
        "potato",
        "chickpea",
        "coconut",
        "almond",
    ),
)
_NUTS = (
    _words(
        "peanut",
        "almond",
        "cashew",
        "walnut",
        "hazelnut",
        "pecan",
        "pistachio",
        "macadamia",
        "pine nut",
        "satay",
        "praline",
        "nut",
    ),
    _words("nut free", "nut-free", "coconut", "nutmeg"),
)
_DIETARY_RULES: dict[str, tuple[tuple[re.Pattern[str], re.Pattern[str]], ...]] = {
    "vegetarian": (_MEAT_AND_FISH,),
    "vegan": (_MEAT_AND_FISH, _DAIRY, _EGGS_AND_HONEY),
    "dairy-free": (_DAIRY,),
    "gluten-free": (_GLUTEN,),
    "nut-free": (_NUTS,),
}


def sample_corpus_candidates(
    corpus: RecipeCorpusStore,
    *,
    pantry_names: Sequence[str],
    dietary_flags: Sequence[str],
    max_total_time_mins: int | None,
    exclude_external_ids: Collection[str],
    rng: random.Random,
    sample_size: int = SAMPLE_SIZE,
    pool_size: int = PANTRY_POOL_SIZE,
) -> list[RecipeSummary]:
    all_recipes, _ = corpus.search(per_page=_EVERYTHING)
    excluded = set(exclude_external_ids)
    rules = [rule for flag in dietary_flags for rule in _DIETARY_RULES.get(flag.strip().casefold(), ())]
    eligible = {
        summary.external_id: summary
        for summary in all_recipes
        if summary.external_id not in excluded
        and _fits_time(summary, max_total_time_mins)
        and _fits_diet(summary, rules)
    }

    pantry_matches: Counter[str] = Counter()
    for name in pantry_names:
        pantry_matches.update(_recipes_using(corpus, name) & eligible.keys())

    # Most pantry items used first; random order within a tier so ties don't favour any recipe.
    tie_breaks = {external_id: rng.random() for external_id in sorted(pantry_matches)}
    ranked = sorted(pantry_matches, key=lambda external_id: (-pantry_matches[external_id], tie_breaks[external_id]))
    pool = ranked[:pool_size]
    picked = rng.sample(pool, min(sample_size, len(pool)))

    if len(picked) < sample_size:
        remaining = sorted(eligible.keys() - set(picked))
        picked += rng.sample(remaining, min(sample_size - len(picked), len(remaining)))
    return [eligible[external_id] for external_id in picked]


def _recipes_using(corpus: RecipeCorpusStore, pantry_name: str) -> set[str]:
    """Recipes matching any meaningful word of a pantry item ("tinned tomatoes" → "tomato")."""
    matched: set[str] = set()
    for token in _TOKEN_RE.findall(pantry_name.casefold()):
        if len(token) < _MIN_TOKEN_LENGTH:
            continue
        hits, _ = corpus.search(q=_singular_prefix(token), per_page=_EVERYTHING)
        matched.update(hit.external_id for hit in hits)
    return matched


def _singular_prefix(token: str) -> str:
    # Search matches word prefixes, so trimming a plural suffix also matches the singular.
    if token.endswith("es") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _fits_time(summary: RecipeSummary, max_total_time_mins: int | None) -> bool:
    return (
        max_total_time_mins is None or summary.total_time_mins is None or summary.total_time_mins <= max_total_time_mins
    )


def _fits_diet(summary: RecipeSummary, rules: Sequence[tuple[re.Pattern[str], re.Pattern[str]]]) -> bool:
    # Ingredients, not titles: a title like "Noodle Bowl" says nothing about rice vs wheat noodles.
    names = [name.casefold() for name in summary.ingredient_names]
    return not any(forbidden.search(name) and not safe.search(name) for forbidden, safe in rules for name in names)
