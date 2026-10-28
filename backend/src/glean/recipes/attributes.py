"""What a recipe is, beyond its own text: the attributes the planner filters and scores on.

The values are the ones settled in G1 (spec 6.1, "Attribute values"). They are a **contract**: the
enrichers that ask the decision model, the projection that carries the answers, the filter and scorer that
read them, and the check-sample tooling that measures them all name these enums and nothing else. A value
that is missing, not yet enriched, or below its confidence bar is `unsure` — never absent — so every recipe
is plannable and an unknown attribute earns no variety credit and no penalty.

`active_time` is a bucket, not minutes: Q3 found the stated time is really schema.org `prepTime`, so V5
estimates hands-on time for every recipe and stores which bucket it falls in. The household cap compares
against the bucket's **upper** bound (`fits_time_cap`), falling back to total time when nothing is known.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "ACTIVE_TIME_QUESTION",
    "ATTRIBUTE_QUESTIONS",
    "CUISINE_QUESTION",
    "DISH_TYPE_QUESTION",
    "MAIN_CARB_QUESTION",
    "MAIN_PROTEIN_QUESTION",
    "UNSURE",
    "WHOLE_FOOD_QUESTION",
    "ActiveTimeBucket",
    "Cuisine",
    "DishType",
    "MainCarb",
    "MainProtein",
    "RecipeAttributes",
    "WholeFood",
    "normalise_cuisine",
]

UNSURE = "unsure"

# The stable question name each attribute's answer is stored under (F1's answer-item key scheme).
MAIN_PROTEIN_QUESTION = "attribute:main_protein"
MAIN_CARB_QUESTION = "attribute:main_carb"
DISH_TYPE_QUESTION = "attribute:dish_type"
CUISINE_QUESTION = "attribute:cuisine"
WHOLE_FOOD_QUESTION = "attribute:whole_food"
ACTIVE_TIME_QUESTION = "active_time:bucket"

# Which question carries which attribute of `RecipeAttributes`, and so what the projection entry stores.
ATTRIBUTE_QUESTIONS: dict[str, str] = {
    "main_protein": MAIN_PROTEIN_QUESTION,
    "main_carb": MAIN_CARB_QUESTION,
    "dish_type": DISH_TYPE_QUESTION,
    "cuisine": CUISINE_QUESTION,
    "whole_food": WHOLE_FOOD_QUESTION,
    "active_time": ACTIVE_TIME_QUESTION,
}


class MainProtein(StrEnum):
    """What the dish is built around. One value per recipe (G1).

    "Chicken and chorizo" counts as chicken, processed meat counts under its animal, and egg-led or
    cheese-led dishes are `vegetarian_other`.
    """

    UNSURE = UNSURE
    CHICKEN = "chicken"
    TURKEY_OR_DUCK = "turkey_or_duck"
    BEEF = "beef"
    PORK = "pork"
    LAMB = "lamb"
    FISH = "fish"
    SEAFOOD = "seafood"
    BEANS_AND_PULSES = "beans_and_pulses"
    TOFU_OR_PLANT_PROTEIN = "tofu_or_plant_protein"
    VEGETARIAN_OTHER = "vegetarian_other"
    MIXED = "mixed"
    NONE = "none"


class MainCarb(StrEnum):
    """The starch the dish is built around. `other_grains` covers couscous, quinoa, bulgur and polenta."""

    UNSURE = UNSURE
    RICE = "rice"
    PASTA = "pasta"
    NOODLES = "noodles"
    POTATO = "potato"
    BREAD_OR_WRAPS = "bread_or_wraps"
    OTHER_GRAINS = "other_grains"
    NONE = "none"


class DishType(StrEnum):
    """The shape of the dish, used for variety. `rice_dish` covers risotto, pilaf and paella."""

    UNSURE = UNSURE
    CURRY = "curry"
    STIR_FRY = "stir_fry"
    PASTA_DISH = "pasta_dish"
    SOUP_OR_STEW = "soup_or_stew"
    ROAST_OR_TRAYBAKE = "roast_or_traybake"
    SALAD_OR_BOWL = "salad_or_bowl"
    HANDHELD = "handheld"
    PIE_OR_BAKE = "pie_or_bake"
    RICE_DISH = "rice_dish"
    PAN_OR_GRILL = "pan_or_grill"
    OTHER = "other"


class Cuisine(StrEnum):
    """About 20 regional values, replacing the 104 raw corpus strings variety scoring used to see.

    "X-Inspired" maps to X and there is no fusion value: a fusion dish is `other` (G1).
    """

    UNSURE = UNSURE
    BRITISH = "british"
    ITALIAN = "italian"
    FRENCH = "french"
    SPANISH = "spanish"
    GREEK = "greek"
    MIDDLE_EASTERN = "middle_eastern"
    NORTH_AFRICAN = "north_african"
    INDIAN = "indian"
    THAI = "thai"
    VIETNAMESE = "vietnamese"
    CHINESE = "chinese"
    JAPANESE = "japanese"
    KOREAN = "korean"
    SOUTHEAST_ASIAN = "southeast_asian"
    MEXICAN = "mexican"
    CARIBBEAN = "caribbean"
    AMERICAN = "american"
    LATIN_AMERICAN = "latin_american"
    OTHER = "other"


class WholeFood(StrEnum):
    """How much of the dish is cooked from unprocessed ingredients (G1)."""

    UNSURE = UNSURE
    WHOLE = "whole"
    MIXED = "mixed"
    PROCESSED = "processed"


class ActiveTimeBucket(StrEnum):
    """Hands-on minutes, as a bucket, because the estimate is a bucket-shaped answer.

    The values are the ones the owner's labels use. `OVER_60` has no upper bound, so it can never be
    certified as fitting a household time cap.
    """

    UNSURE = UNSURE
    UP_TO_15 = "<=15"
    FROM_15_TO_30 = "15-30"
    FROM_30_TO_45 = "30-45"
    FROM_45_TO_60 = "45-60"
    OVER_60 = "60+"

    @property
    def upper_bound_mins(self) -> int | None:
        """The most minutes this bucket can mean, or None when it has no upper bound (or isn't known)."""
        return {
            ActiveTimeBucket.UP_TO_15: 15,
            ActiveTimeBucket.FROM_15_TO_30: 30,
            ActiveTimeBucket.FROM_30_TO_45: 45,
            ActiveTimeBucket.FROM_45_TO_60: 60,
        }.get(self)

    @classmethod
    def from_text(cls, value: Any) -> ActiveTimeBucket:
        """The bucket a label spells, in the ways one gets written.

        Tolerates the spec's `\u2264` ("at most"), a plain `<`, an en dash range, "15to30" and a trailing unit, because
        a label is written by hand and a bucket it names should score rather than read as unreadable.
        """
        if not isinstance(value, str):
            return cls.UNSURE
        text = value.strip().casefold().replace("\u2013", "-").replace("\u2264", "<=").replace(" ", "")
        for unit in ("minutes", "minute", "mins", "min"):
            text = text.replace(unit, "")
        return _BUCKET_SPELLINGS.get(text, cls.UNSURE)


_BUCKET_SPELLINGS: dict[str, ActiveTimeBucket] = {
    "<=15": ActiveTimeBucket.UP_TO_15,
    "\u226415": ActiveTimeBucket.UP_TO_15,  # the spec's own "\u226415" spelling
    "<15": ActiveTimeBucket.UP_TO_15,
    "0-15": ActiveTimeBucket.UP_TO_15,
    "under15": ActiveTimeBucket.UP_TO_15,
    "15-30": ActiveTimeBucket.FROM_15_TO_30,
    "15to30": ActiveTimeBucket.FROM_15_TO_30,
    "30-45": ActiveTimeBucket.FROM_30_TO_45,
    "45-60": ActiveTimeBucket.FROM_45_TO_60,
    "60+": ActiveTimeBucket.OVER_60,
    "60plus": ActiveTimeBucket.OVER_60,
    "over60": ActiveTimeBucket.OVER_60,
    "unsure": ActiveTimeBucket.UNSURE,
}

# Spellings of the G1 names a labeller or an importer might write, mapped onto the enum's own value.
_CUISINE_SYNONYMS: dict[str, Cuisine] = {
    "british": Cuisine.BRITISH,
    "english": Cuisine.BRITISH,
    "italian": Cuisine.ITALIAN,
    "french": Cuisine.FRENCH,
    "spanish": Cuisine.SPANISH,
    "greek": Cuisine.GREEK,
    "middleeastern": Cuisine.MIDDLE_EASTERN,
    "lebanese": Cuisine.MIDDLE_EASTERN,
    "turkish": Cuisine.MIDDLE_EASTERN,
    "persian": Cuisine.MIDDLE_EASTERN,
    "northafrican": Cuisine.NORTH_AFRICAN,
    "moroccan": Cuisine.NORTH_AFRICAN,
    "indian": Cuisine.INDIAN,
    "thai": Cuisine.THAI,
    "vietnamese": Cuisine.VIETNAMESE,
    "chinese": Cuisine.CHINESE,
    "japanese": Cuisine.JAPANESE,
    "korean": Cuisine.KOREAN,
    "southeastasian": Cuisine.SOUTHEAST_ASIAN,
    "indonesian": Cuisine.SOUTHEAST_ASIAN,
    "malaysian": Cuisine.SOUTHEAST_ASIAN,
    "filipino": Cuisine.SOUTHEAST_ASIAN,
    "mexican": Cuisine.MEXICAN,
    "caribbean": Cuisine.CARIBBEAN,
    "american": Cuisine.AMERICAN,
    "latinamerican": Cuisine.LATIN_AMERICAN,
    "other": Cuisine.OTHER,
}

# The separators a compound corpus value uses: "Thai, Thai-Inspired", "Indian & British".
_CUISINE_SPLIT = ("/", ",", "&", ";", " and ", " with ")

# A qualifier in brackets, which the G1 table itself uses: "Southeast Asian (other)". It names the region's
# place in the list, not a different cuisine, so it is dropped before the lookup.
_CUISINE_QUALIFIER = re.compile(r"\([^)]*\)")


def normalise_cuisine(value: Any) -> Cuisine | None:
    """The G1 cuisine a raw string means, or None when it names no cuisine we know.

    One place for the spellings, so the import, the check-sample labels and the enricher's answers agree:
    "X-Inspired" maps to X, a compound value resolves to its first known part, and there is no fusion value.
    """
    if not isinstance(value, str):
        return None
    parts = [value.strip().casefold()]
    for separator in _CUISINE_SPLIT:
        parts = [part for chunk in parts for part in chunk.split(separator)]
    for part in (part.strip() for part in parts):
        part = _CUISINE_QUALIFIER.sub(" ", part)
        part = part.removesuffix("-inspired").removesuffix(" inspired")
        part = part.replace("-", "").replace("_", "").replace(" ", "")
        if part in _CUISINE_SYNONYMS:
            return _CUISINE_SYNONYMS[part]
    return None


class RecipeAttributes(BaseModel):
    """Everything the filter and scorer need about a recipe, one value each, `unsure` where unknown."""

    model_config = ConfigDict(frozen=True)

    main_protein: MainProtein = MainProtein.UNSURE
    main_carb: MainCarb = MainCarb.UNSURE
    dish_type: DishType = DishType.UNSURE
    cuisine: Cuisine = Cuisine.UNSURE
    whole_food: WholeFood = WholeFood.UNSURE
    active_time: ActiveTimeBucket = ActiveTimeBucket.UNSURE

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None) -> RecipeAttributes:
        """Read the projection's plain mapping, treating anything missing or unreadable as `unsure`."""
        values = values or {}
        return cls(
            main_protein=_coerce(MainProtein, values.get("main_protein")),
            main_carb=_coerce(MainCarb, values.get("main_carb")),
            dish_type=_coerce(DishType, values.get("dish_type")),
            cuisine=normalise_cuisine(values.get("cuisine")) or Cuisine.UNSURE,
            whole_food=_coerce(WholeFood, values.get("whole_food")),
            active_time=ActiveTimeBucket.from_text(values.get("active_time")),
        )

    def as_mapping(self) -> dict[str, str]:
        """The same attributes as plain strings, which is what a projection entry stores."""
        return {
            "main_protein": self.main_protein.value,
            "main_carb": self.main_carb.value,
            "dish_type": self.dish_type.value,
            "cuisine": self.cuisine.value,
            "whole_food": self.whole_food.value,
            "active_time": self.active_time.value,
        }

    def active_time_mins(self, total_time_mins: int | None) -> int | None:
        """The most hands-on minutes this recipe can take: the bucket's bound, capped by its total time.

        Hands-on time can never exceed the time the recipe takes overall, so a bucket whose upper bound is
        above the total is only as slow as the total (a 30-45 estimate on a 35-minute recipe is 35). With no
        upper bound — `60+`, or nothing measured yet — the total time is the only bound there is; with neither,
        nothing is known. This is the number the household's cap is compared against and the one a label shows.
        """
        bound = self.active_time.upper_bound_mins
        if total_time_mins is None:
            return bound
        return total_time_mins if bound is None else min(bound, total_time_mins)

    def fits_time_cap(self, cap_mins: int | None, *, total_time_mins: int | None) -> bool:
        """Whether the household's time cap admits this recipe.

        The cap is compared against the bucket's upper bound (spec 6.1). `OVER_60` means at least an hour of
        hands-on work, so a cap under 60 rejects it however short its total time is; a cap of an hour or more
        can't be decided by the bucket alone, so it falls through to total time. With no bucket — not enriched
        yet, or below its bar — total time decides, as it did before V5. An unknown total time passes, as it
        did before: a missing field is not evidence the recipe is slow.
        """
        if cap_mins is None:
            return True
        if self.active_time is ActiveTimeBucket.OVER_60 and cap_mins < 60:
            return False
        bound = self.active_time_mins(total_time_mins)
        return bound is None or bound <= cap_mins


def _coerce[EnumT: StrEnum](enum: type[EnumT], value: Any) -> EnumT:
    """The enum member `value` names, or its `unsure` member when it names none.

    Stored values are already the enum's own value; the extra spellings (`stir fry`, `bread-or-wraps`)
    only exist so a hand-written label or an older projection never reads as a hard failure.
    """
    unsure = enum(UNSURE)
    if not isinstance(value, str):
        return unsure
    text = value.strip().casefold()
    for candidate in (text, text.replace(" ", "_").replace("-", "_")):
        try:
            return enum(candidate)
        except ValueError:
            continue
    return unsure
