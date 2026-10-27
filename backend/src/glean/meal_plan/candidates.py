"""Choose which corpus recipes to offer the meal-plan model.

The model never sees the whole corpus. Recipes are ranked by the urgency-weighted fit of
the pantry items they use (via the corpus search index), a random sample of the best
matches becomes the candidate list, and random other recipes top it up when the pantry
matches too few. Randomness keeps repeated Generate taps varied.

Two rules stop a perishable going off unused. A recipe using an item that expires within
`URGENT_EXPIRY_DAYS` is always in the candidate list, whatever the sampling picks (bounded
by `GUARANTEE_MAX`, which only changes *which* recipes are offered, never how many). And
every pantry match counts for as much as the item's urgency score, not as a flat one, so a
recipe using the most urgent item outranks one using several unfussy staples.

Dietary flags are applied here, before sampling, because the corpus carries no dietary
metadata of its own: a recipe is excluded when the stored decision for (recipe, flag) says
it probably breaks the flag, or when there is no current decision. Flags the decision
model isn't asked about (Keto, Paleo) are left to the meal-plan model.

Those flags, the profile's disliked ingredients (V13b, `meal_plan.household`), the household's
time cap and the meals already planned are hard constraints: `meal_plan.eligibility` applies the
six-week recency floor on top of them and never relaxes one to satisfy the other.

The household's time cap is applied here too, against the enriched active-time
bucket's upper bound (spec 6.1): the cap is about hands-on work, and a
60-minute total of which 10 minutes is hands-on fits a 20-minute cap. With no
bucket — not enriched yet, or below its bar — it falls back to total time as it
did before V5.

The guarantee is narrower than either. It never revives a recipe a hard constraint dropped, and
it never reaches past a floor that held. When the floor has relaxed it covers each urgent item
from the fresh recipes first and falls back to a relaxed recipe only for an item no fresh recipe
uses -- that recipe is eligible per spec §6.2 step 2 and still carries its age as a fallback.
Relaxed recipes never take a slot a fresh recipe could have filled.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from glean.meal_plan.dietary_decisions import CALIBRATED_DIETARY, DietaryDecisions, DietaryDecisionStore
from glean.meal_plan.eligibility import MIN_ELIGIBLE_PER_SLOT, apply_recency_floor
from glean.observability import logger
from glean.recipes.answers import content_fingerprint
from glean.recipes.attributes import RecipeAttributes
from glean.recipes.enrichment.projection_attributes import attributes_from_answers

if TYPE_CHECKING:
    import random
    from collections.abc import Callable, Collection, Iterable, Mapping, Sequence

    from glean.meal_plan.eligibility import CookedMeal
    from glean.recipes.answers import RecipeAnswer
    from glean.recipes.corpus import RecipeCorpusStore
    from glean.recipes.search_index import RecipeSummary

SAMPLE_SIZE = 25
PANTRY_POOL_SIZE = 60
# An item expiring within this many days must reach the model, whatever the sampling picks.
URGENT_EXPIRY_DAYS = 3
# Cap on guaranteed inclusions: 10 of a 25-recipe sample leaves the rest of the list free to vary
# between Generate taps, and keeps the prompt the same size it was before the guarantee existed.
GUARANTEE_MAX = 10

_EVERYTHING = 1_000_000
_TOKEN_RE = re.compile(r"\w+")
_MIN_TOKEN_LENGTH = 3
_NEAR_DUPLICATE_OVERLAP = 0.7


@dataclass(frozen=True)
class OfferedRecipe:
    """One corpus recipe handed to the meal-plan model.

    `cooked_days_ago` is set only for a recipe the recency floor relaxed back in: it was cooked that
    recently and is offered as a fallback, which the prompt tells the model to prefer against. The
    scorer will read the same age to apply `eligibility.recency_penalty`.
    """

    summary: RecipeSummary
    cooked_days_ago: float | None = None
    # The urgency-weighted pantry fit the sampler ranked this recipe by, kept so the scorer (V6) can use the
    # ranking the household was actually offered rather than recomputing it from the corpus.
    pantry_fit: float = 0.0

    @property
    def external_id(self) -> str:
        return self.summary.external_id

    @property
    def title(self) -> str:
        return self.summary.title


@dataclass(frozen=True)
class PantryItem:
    """One item of the pantry slice the request carries.

    `urgency_score` is the app's urgency for the item; an item the caller knows only by name weighs 1,
    which is how every pantry match counted before urgency weighting. `expires_in_days` is the whole
    number of days until the item goes off, or None when the expiry date is unknown -- the server
    cannot recover it from `urgency_score`.
    """

    name: str
    urgency_score: float | None = None
    expires_in_days: int | None = None

    @property
    def is_urgent(self) -> bool:
        """Whether this item goes off soon enough that a recipe using it must be offered."""
        return self.expires_in_days is not None and self.expires_in_days <= URGENT_EXPIRY_DAYS

    @property
    def weight(self) -> float:
        """How much one recipe using this item counts towards that recipe's pantry fit."""
        return 1.0 if self.urgency_score is None else self.urgency_score


def sample_corpus_candidates(
    corpus: RecipeCorpusStore,
    *,
    pantry: Sequence[PantryItem],
    dietary_flags: Sequence[str],
    max_total_time_mins: int | None,
    exclude_external_ids: Collection[str],
    rng: random.Random,
    cooked: Sequence[CookedMeal] = (),
    slots: int = 1,
    now: datetime | None = None,
    sample_size: int = SAMPLE_SIZE,
    pool_size: int = PANTRY_POOL_SIZE,
    guarantee_max: int = GUARANTEE_MAX,
    preferred_ids: Collection[str] = (),
    narrowing: Mapping[str, Callable[[RecipeAttributes, int | None], bool]] | None = None,
    disliked_ingredients: Sequence[str] = (),
    favourite_meals: Sequence[tuple[str, str | None]] = (),
    profile_reserve: Sequence[tuple[Callable[[RecipeAttributes], bool], int]] = (),
) -> list[OfferedRecipe]:
    """Up to `sample_size` distinct corpus recipes to offer the meal-plan model.

    Every pantry item going off within `URGENT_EXPIRY_DAYS` gets a recipe using it (up to
    `guarantee_max` recipes, one per item before any item gets a second), and those lead the list.
    `cooked` is the household's history window and `slots` the number of meals this request plans;
    together they drive `eligibility.apply_recency_floor`. Recipes it relaxed back in are offered last,
    so they reach the candidate list only after every fresh recipe, and they carry `cooked_days_ago` so
    the model sees them as the fallback they are. `preferred_ids` (last week's dinners, under the "same as
    last week" chip) are offered right after the urgent guarantee, when they are fresh and eligible.
    `narrowing` maps a chip to its rule (`tools.chip_narrows`); see `_narrowed` for when it applies.
    `disliked_ingredients` are the profile's: a recipe using one is never offered, floor or no floor. The rest of
    the profile ranks the offer (spec 6.2 step 5): `favourite_meals` (text, matched recipe id) that are fresh and
    eligible are offered with `preferred_ids`, and each `profile_reserve` rule (a liked cuisine, a protein minimum)
    takes up to its count of fresh recipes it matches, in seeded order. Neither draws on `rng` when it is empty, so a
    household without a profile is offered exactly what it was before.
    """
    all_recipes, _ = corpus.search(per_page=_EVERYTHING)
    excluded = set(exclude_external_ids)
    diet_excluded = dietary_excluded_ids(corpus, all_recipes, dietary_flags)
    from glean.meal_plan.household import disliked_recipe_ids, favourite_ids  # noqa: PLC0415 - imports mentions_item

    disliked = disliked_recipe_ids(
        ((summary.external_id, summary.ingredient_names) for summary in all_recipes), disliked_ingredients
    )
    # Only read when a cap is set: with no cap every recipe fits, so the answers are not worth loading.
    attributes = (
        recipe_attributes(corpus, all_recipes)
        if max_total_time_mins is not None or narrowing or profile_reserve
        else {}
    )
    # Hard constraints only: the recency floor is applied to what survives them, and relaxing the
    # floor must never bring back a recipe a flag, the time cap or an already-planned meal ruled out.
    eligible = {
        summary.external_id: summary
        for summary in all_recipes
        if summary.external_id not in excluded
        and _fits_time(summary, max_total_time_mins, attributes.get(summary.external_id, RecipeAttributes()))
        and summary.external_id not in diet_excluded
        and summary.external_id not in disliked
    }
    if narrowing:
        eligible = _narrowed(
            eligible,
            narrowing,
            attributes=attributes,
            cooked=cooked,
            now=now or datetime.now(UTC),
            slots=slots,
            keep=preferred_ids,
        )
    floor = apply_recency_floor(
        eligible,
        titles={external_id: summary.title for external_id, summary in eligible.items()},
        cooked=cooked,
        now=now or datetime.now(UTC),
        slots=slots,
    )
    floor_ids = set(floor.recipe_ids)
    if floor.disliked:
        # A deliberate exclusion, not an empty corpus: logged so an eval can tell "nothing was rated" from
        # "the household's thumbs left too few recipes".
        logger.info("thumbs-down recipes left out", extra={"disliked": len(floor.disliked)})
    if floor.relaxed_floor:
        # The soft repeat rule gave way because the hard constraints left too few fresh recipes. Reported
        # so eval runs and logs can tell "no repeats" from "no repeats because the floor never relaxed".
        logger.info("recency floor relaxed", extra={"recently_cooked": len(floor.relaxed), "slots": slots})

    fit = _pantry_fit(corpus, pantry, floor_ids)
    fresh = set(floor.fresh)
    # Random order within a tier so ties don't favour any recipe, drawn in id order so one seed is enough.
    tie_breaks = {external_id: rng.random() for external_id in sorted(fit)}
    guarantee_limit = min(guarantee_max, sample_size)

    # Most pantry fit first; random order within a tier so ties don't favour any recipe.
    ranked = sorted(fit, key=lambda external_id: (-fit[external_id], tie_breaks[external_id]))
    # Recipes that came back when the floor relaxed are the least preferred: they trail the fresh ones
    # and never displace one, so a week with enough fresh recipes never offers a recent repeat. The
    # scorer will instead subtract recency_penalty from their fit (spec §6.2).
    fresh_ranked = [recipe_id for recipe_id in ranked if recipe_id in fresh]
    relaxed_ranked = [recipe_id for recipe_id in ranked if recipe_id not in fresh]
    picked: list[RecipeSummary] = []
    urgent_uses = _ingredient_urgent_uses(eligible.values(), pantry)
    # Fresh coverage is guaranteed first, so neither the random sample nor a relaxed recipe can crowd an
    # urgent fresh recipe out of the list. A floor that held is never undone here: those recipes are not
    # in `fresh` at all. When the floor relaxed, its relaxed recipes get their own coverage below, after
    # every fresh recipe, and only for an urgent item no fresh recipe uses.
    guaranteed = _guaranteed_recipe_ids(
        urgent_uses,
        eligible_ids=fresh,
        fit=fit,
        tie_breaks=tie_breaks,
        limit=guarantee_limit,
    )
    _take_distinct(picked, [eligible[recipe_id] for recipe_id in guaranteed], guarantee_limit)
    favourites = favourite_ids(((recipe_id, summary.title) for recipe_id, summary in eligible.items()), favourite_meals)
    preferred = [eligible[recipe_id] for recipe_id in sorted({*preferred_ids, *favourites}) if recipe_id in fresh]
    _take_distinct(picked, preferred, sample_size)
    if profile_reserve:
        shuffled = sorted(fresh)
        rng.shuffle(shuffled)
        for wanted, count in profile_reserve:
            matching = [
                eligible[recipe_id] for recipe_id in shuffled if wanted(attributes.get(recipe_id, RecipeAttributes()))
            ]
            _take_distinct(picked, matching, min(sample_size, len(picked) + count))

    _fill_partition(
        picked,
        floor.fresh,
        fresh_ranked,
        eligible=eligible,
        rng=rng,
        sample_size=sample_size,
        pool_size=pool_size,
    )
    relaxed = set(floor.relaxed)
    if relaxed:
        # Step 4 of spec §6.2 runs over what step 2 left eligible, and step 2 brought these back. An
        # urgent item no fresh recipe uses is covered here, after every fresh recipe, so it takes only a
        # slot the fresh ones left empty. Where a fresh recipe does use the item, fresh is preferred and
        # the relaxed recipes are left to the ordinary sampling.
        relaxed_guaranteed = _guaranteed_recipe_ids(
            _urgent_uses_no_fresh_recipe_covers(urgent_uses, fresh=fresh),
            eligible_ids=relaxed,
            fit=fit,
            tie_breaks=tie_breaks,
            limit=guarantee_limit,
        )
        _take_distinct(picked, [eligible[recipe_id] for recipe_id in relaxed_guaranteed], sample_size)
        _fill_partition(
            picked,
            floor.relaxed,
            relaxed_ranked,
            eligible=eligible,
            rng=rng,
            sample_size=sample_size,
            pool_size=pool_size,
        )
    return [
        OfferedRecipe(
            summary=summary,
            cooked_days_ago=(floor.days_since_cooked[summary.external_id] if summary.external_id in relaxed else None),
            pantry_fit=fit.get(summary.external_id, 0.0),
        )
        for summary in picked
    ]


def dietary_excluded_ids(
    corpus: RecipeCorpusStore, summaries: Iterable[RecipeSummary], dietary_flags: Sequence[str]
) -> frozenset[str]:
    """The recipes the stored dietary decisions rule out for these flags, or that no current decision covers.

    One read of the decision store. The sampler and `pipeline.tool_context` both call it, so the agent's
    `get_eligible_recipes` and the offered candidates exclude exactly the same recipes.
    """
    flags = [flag.strip().casefold() for flag in dietary_flags]
    if not flags:
        return frozenset()
    decisions = DietaryDecisions(DietaryDecisionStore(corpus.store).load(), calibration=CALIBRATED_DIETARY)
    return frozenset(
        summary.external_id for summary in summaries if any(decisions.excludes(summary, flag) for flag in flags)
    )


def _fill_from(
    picked: list[RecipeSummary],
    recipe_ids: Iterable[str],
    *,
    eligible: Mapping[str, RecipeSummary],
    rng: random.Random,
    sample_size: int,
) -> None:
    """Append shuffled `recipe_ids` to `picked` until `sample_size`, skipping near-duplicates."""
    remaining = sorted(set(recipe_ids) - {summary.external_id for summary in picked})
    if not remaining or len(picked) >= sample_size:
        return
    _take_distinct(picked, [eligible[recipe_id] for recipe_id in rng.sample(remaining, len(remaining))], sample_size)


def _narrowed(
    eligible: Mapping[str, RecipeSummary],
    narrowing: Mapping[str, Callable[[RecipeAttributes, int | None], bool]],
    *,
    attributes: Mapping[str, RecipeAttributes],
    cooked: Sequence[CookedMeal],
    now: datetime,
    slots: int,
    keep: Collection[str] = (),
) -> dict[str, RecipeSummary]:
    """The hard-constraint pool, narrowed by each chip in turn while at least three fresh recipes per slot pass.

    Counted on fresh recipes (the six-week floor's), so a chip never forces the floor to relax and offer a
    recent repeat. A chip that would leave too few is skipped, and pays its +2 in the scorer instead; each chip
    is decided on what the chips before it left. Hard constraints were applied before this, so narrowing can
    only remove recipes.

    `keep` (last week's dinners, under "same as last week") survives every chip: the household asked for those
    dinners by name, which is more explicit than a chip's rule. They count towards a chip's threshold only when
    they match it, so they never talk a chip into narrowing.
    """
    narrowed = dict(eligible)
    fresh = set(
        apply_recency_floor(
            narrowed,
            titles={external_id: summary.title for external_id, summary in narrowed.items()},
            cooked=cooked,
            now=now,
            slots=slots,
        ).fresh
    )
    needed = MIN_ELIGIBLE_PER_SLOT * slots
    for chip, passes in narrowing.items():
        kept = {
            external_id
            for external_id, summary in narrowed.items()
            if passes(attributes.get(external_id, RecipeAttributes()), summary.total_time_mins)
        }
        if len(kept & fresh) >= needed:
            narrowed = {
                external_id: summary
                for external_id, summary in narrowed.items()
                if external_id in kept or external_id in keep
            }
            fresh &= kept
            logger.info("a chip narrowed the offer", extra={"chip": chip, "recipes": len(narrowed)})
        else:
            logger.info(
                "a chip fell back to its score term",
                extra={"chip": chip, "fresh_matching": len(kept & fresh), "needed": needed},
            )
    return narrowed


def _fill_partition(
    picked: list[RecipeSummary],
    group: Sequence[str],
    pantry_ranked: Sequence[str],
    *,
    eligible: Mapping[str, RecipeSummary],
    rng: random.Random,
    sample_size: int,
    pool_size: int,
) -> None:
    """Fill from one partition: its pantry-ranked pool first, then the rest of the partition."""
    _fill_from(picked, pantry_ranked[:pool_size], eligible=eligible, rng=rng, sample_size=sample_size)
    _fill_from(
        picked,
        set(group) - set(pantry_ranked[:pool_size]),
        eligible=eligible,
        rng=rng,
        sample_size=sample_size,
    )


def _urgent_uses_no_fresh_recipe_covers(
    urgent_uses: Mapping[str, Sequence[PantryItem]], *, fresh: Collection[str]
) -> dict[str, tuple[PantryItem, ...]]:
    """The urgent uses of recipes the floor relaxed, for items no fresh recipe uses at all."""
    covered_by_fresh = {item for recipe_id, items in urgent_uses.items() if recipe_id in fresh for item in items}
    uncovered: dict[str, tuple[PantryItem, ...]] = {}
    for recipe_id, items in urgent_uses.items():
        if recipe_id in fresh:
            continue
        remaining = tuple(item for item in items if item not in covered_by_fresh)
        if remaining:
            uncovered[recipe_id] = remaining
    return uncovered


def _guaranteed_recipe_ids(
    urgent_uses: Mapping[str, Sequence[PantryItem]],
    *,
    eligible_ids: Collection[str],
    fit: Mapping[str, float],
    tie_breaks: Mapping[str, float],
    limit: int,
) -> list[str]:
    """Recipes to guarantee, covering every urgent item before any item gets a second recipe.

    The cap is a prompt and variety bound, so it can be smaller than the number of recipes using urgent
    items: spending it on the highest urgency scores alone lets one well-stocked urgent item take every
    slot and starve the lone coriander recipe. So every urgent item is covered first, most urgent item
    first (soonest to go off), with one recipe counting once however many of them it uses; only then is
    what is left of the bound spent on the strongest remaining urgent matches.
    """
    by_item = _recipes_by_urgent_item(urgent_uses, eligible_ids=eligible_ids, fit=fit, tie_breaks=tie_breaks)
    guaranteed = _cover_urgent_items(by_item, urgent_uses, limit=limit)
    return _with_extra_urgent_recipes(guaranteed, by_item, fit=fit, tie_breaks=tie_breaks, limit=limit)


def _recipes_by_urgent_item(
    urgent_uses: Mapping[str, Sequence[PantryItem]],
    *,
    eligible_ids: Collection[str],
    fit: Mapping[str, float],
    tie_breaks: Mapping[str, float],
) -> dict[PantryItem, list[str]]:
    """Each urgent item's eligible recipes, best fit first."""
    by_item: dict[PantryItem, list[str]] = {}
    for recipe_id, items in urgent_uses.items():
        if recipe_id not in eligible_ids:
            continue
        for item in items:
            by_item.setdefault(item, []).append(recipe_id)
    for recipe_ids in by_item.values():
        recipe_ids.sort(key=lambda recipe_id: (-fit.get(recipe_id, 0.0), tie_breaks.get(recipe_id, 0.0)))
    return by_item


def _cover_urgent_items(
    by_item: Mapping[PantryItem, Sequence[str]],
    urgent_uses: Mapping[str, Sequence[PantryItem]],
    *,
    limit: int,
) -> list[str]:
    """One recipe per urgent item, most urgent item first, skipping items a reserved recipe covers."""
    most_urgent_first = sorted(
        by_item, key=lambda urgent_item: (urgent_item.expires_in_days or 0, urgent_item.name.casefold())
    )
    guaranteed: list[str] = []
    covered: set[PantryItem] = set()
    for item in most_urgent_first:
        if item in covered:
            # A recipe already reserved uses this item too; reserving another would waste the bound.
            continue
        if len(guaranteed) >= limit:
            break
        recipe_id = next((recipe_id for recipe_id in by_item[item] if recipe_id not in guaranteed), None)
        if recipe_id is not None:
            guaranteed.append(recipe_id)
            covered.update(urgent_uses[recipe_id])
    return guaranteed


def _with_extra_urgent_recipes(
    guaranteed: list[str],
    by_item: Mapping[PantryItem, Sequence[str]],
    *,
    fit: Mapping[str, float],
    tie_breaks: Mapping[str, float],
    limit: int,
) -> list[str]:
    """Spend what is left of the bound on the strongest remaining urgent matches."""
    rest = sorted(
        (recipe_id for recipe_ids in by_item.values() for recipe_id in recipe_ids[1:] if recipe_id not in guaranteed),
        key=lambda recipe_id: (-fit.get(recipe_id, 0.0), tie_breaks.get(recipe_id, 0.0)),
    )
    for recipe_id in rest:
        if len(guaranteed) >= limit:
            break
        if recipe_id not in guaranteed:
            guaranteed.append(recipe_id)
    return guaranteed


def _pantry_fit(
    corpus: RecipeCorpusStore, pantry: Sequence[PantryItem], recipe_ids: Collection[str]
) -> dict[str, float]:
    """Urgency-weighted pantry fit per recipe, for the recipes in `recipe_ids`.

    Uses the corpus search, so it is a discovery heuristic: it ranks what the model might like to see.
    Anything the plan then *claims* about a recipe (that it uses up the coriander) comes from
    `_ingredient_urgent_uses` instead, which reads the recipe's own ingredient lines.
    """
    wanted = set(recipe_ids)
    fit: dict[str, float] = {}
    for item in pantry:
        for external_id in _recipes_using(corpus, item.name) & wanted:
            fit[external_id] = fit.get(external_id, 0.0) + item.weight
    return fit


def urgent_pantry_uses(
    corpus: RecipeCorpusStore, pantry: Sequence[PantryItem], recipe_ids: Collection[str]
) -> dict[str, tuple[PantryItem, ...]]:
    """Which urgent pantry items each of `recipe_ids` uses, for naming them in its reason.

    Same evidence as the guarantee, so a recipe promised into the candidate list because it uses the
    coriander is the recipe whose reason can say so.
    """
    wanted = set(recipe_ids)
    summaries = [summary for summary in corpus.search(per_page=_EVERYTHING)[0] if summary.external_id in wanted]
    return _ingredient_urgent_uses(summaries, pantry)


def _ingredient_urgent_uses(
    recipes: Iterable[RecipeSummary], pantry: Sequence[PantryItem]
) -> dict[str, tuple[PantryItem, ...]]:
    """Which urgent pantry items each recipe's ingredient lines name, in the order the pantry carries them."""
    urgent = [item for item in pantry if item.is_urgent]
    uses: dict[str, tuple[PantryItem, ...]] = {}
    for summary in recipes:
        named = tuple(
            item for item in urgent if any(mentions_item(name, item.name) for name in summary.ingredient_names)
        )
        if named:
            uses[summary.external_id] = named
    return uses


def mentions_item(text: str, item_name: str) -> bool:
    """Whether `text` names the whole item, in order: "red onion" is not "red pepper" or "onion soup".

    Ingredient lines and reason text both go through this, so a claim about a recipe and the check that
    the claim was made cannot disagree. Word boundaries matter ("lime" never matches "slime"), a leading
    modifier is part of the identity ("ground coriander" needs "ground"), and every word is compared as
    a set of plausible singulars, so "chillies" and "chilli" meet however the plural was formed.
    """
    words = _item_words(text)
    wanted = _item_words(item_name)
    if not wanted:
        return False
    runs = range(len(words) - len(wanted) + 1)
    return any(all(words[start + offset] & word for offset, word in enumerate(wanted)) for start in runs)


def _item_words(text: str) -> list[frozenset[str]]:
    return [singular_forms(word) for word in _TOKEN_RE.findall(text.casefold()) if len(word) >= _MIN_TOKEN_LENGTH]


# Plurals no suffix rule gets right. "-ves" is listed rather than ruled on: "cloves" is "clove".
_IRREGULAR_SINGULARS = {
    "leaves": "leaf",
    "loaves": "loaf",
    "halves": "half",
    "knives": "knife",
    "wives": "wife",
    "shelves": "shelf",
    "calves": "calf",
    "elves": "elf",
    "scarves": "scarf",
    "thieves": "thief",
}


def singular_forms(word: str) -> frozenset[str]:
    """The word plus every singular an English plural of it could have come from.

    A single rule cannot know whether "chillies" came from "chilli" or "chilly", or whether "cookies"
    is "cookie", so the candidates are kept and two words match when their sets intersect. Ingredient
    identity, not a search prefix: the prefix trimming `_search_prefix` does for FTS ("limes" → "lim")
    never could meet "lime".
    """
    forms = {word, word.removesuffix("s")} if len(word) > 3 else {word}
    if word in _IRREGULAR_SINGULARS:
        forms.add(_IRREGULAR_SINGULARS[word])
    if word.endswith("ies") and len(word) > 4:
        forms.update({f"{word[:-3]}y", f"{word[:-3]}i", f"{word[:-3]}ie"})
    if word.endswith(("ches", "shes", "sses", "xes", "zes")) and len(word) > 4:
        forms.add(word[:-2])
    if word.endswith("oes") and len(word) > 4:
        forms.add(word[:-2])
    return frozenset(forms)


def _take_distinct(picked: list[RecipeSummary], shuffled: Sequence[RecipeSummary], limit: int) -> None:
    """Append recipes in order until `limit`, skipping near-duplicates of ones already picked."""
    for summary in shuffled:
        if len(picked) >= limit:
            return
        if not any(_near_duplicate(summary, existing) for existing in picked):
            picked.append(summary)


def _near_duplicate(a: RecipeSummary, b: RecipeSummary) -> bool:
    return near_duplicate_ingredients(a.ingredient_names, b.ingredient_names)


def near_duplicate_ingredients(a: Iterable[str], b: Iterable[str]) -> bool:
    """Whether two ingredient lists are one dish's variants (chicken breast / thigh / meat-free).

    Offering several wastes candidate slots and the model tends to pick them together. Public because
    `tools.get_eligible_recipes` suppresses the same near-duplicates the sampler does.
    """
    ingredients_a, ingredients_b = _ingredient_set(a), _ingredient_set(b)
    if not ingredients_a or not ingredients_b:
        return False
    return len(ingredients_a & ingredients_b) / len(ingredients_a | ingredients_b) >= _NEAR_DUPLICATE_OVERLAP


def _ingredient_set(names: Iterable[str]) -> set[str]:
    return {" ".join(_TOKEN_RE.findall(name.casefold())) for name in names}


def _recipes_using(corpus: RecipeCorpusStore, pantry_name: str) -> set[str]:
    """Recipes matching any meaningful word of a pantry item ("tinned tomatoes" → "tomato")."""
    matched: set[str] = set()
    for token in _TOKEN_RE.findall(pantry_name.casefold()):
        if len(token) < _MIN_TOKEN_LENGTH:
            continue
        hits, _ = corpus.search(q=_search_prefix(token), per_page=_EVERYTHING)
        matched.update(hit.external_id for hit in hits)
    return matched


def _search_prefix(token: str) -> str:
    # Search matches word prefixes, so trimming a plural suffix also matches the singular.
    if token.endswith("es") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _fits_time(summary: RecipeSummary, max_total_time_mins: int | None, attributes: RecipeAttributes) -> bool:
    """The cap against the bucket's upper bound, and total time when no bucket is known (spec 6.1)."""
    return attributes.fits_time_cap(max_total_time_mins, total_time_mins=summary.total_time_mins)


def recipe_attributes(corpus: RecipeCorpusStore, summaries: Iterable[RecipeSummary]) -> dict[str, RecipeAttributes]:
    """Each summary's attributes, from the same stored answers the projection is built from.

    Public because planning reads attributes through it twice: the sampler for the household's time cap, and
    `pipeline.prepare` for the labels a proposal card shows.

    The answers are read once, not from the projection document: it is the backend's own cache, and the
    seam every backend shares is `answers()`. An answer counts only while it is current for the summary as
    it stands, which is the rule the projection uses too, so the two cannot disagree.
    """
    answers: dict[str, list[RecipeAnswer]] = {}
    for answer in corpus.answers():
        answers.setdefault(answer.recipe_id, []).append(answer)
    return {
        summary.external_id: attributes_from_answers(
            answers.get(summary.external_id, ()),
            content_hash=content_fingerprint(summary.title, summary.ingredient_names),
        )
        for summary in summaries
    }
