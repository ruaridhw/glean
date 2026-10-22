"""The dietary enricher: one probability per (recipe, dietary flag), asked as one `noul` per flag.

This is the first enricher (#125/#159), and the questions, wording and thresholds are the ones the
producer used before the enrichment package existed — carried across unchanged, because a stored answer
is only current while its criteria hash matches and a wording edit would void every answer in the corpus.

The stored value is the probability itself. The threshold is not a confidence floor: it is the
probability at which planning excludes a recipe, applied when the decision is read (`DietaryDecisions`),
which is why the bar here is declared `SafeSide.LOW` (a low probability means "does not break the flag").
ADR 0011 holds the policy, ADR 0025 the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from glean.decisions import NoulCriteria, NoulQuestion
from glean.recipes.answers import dietary_question
from glean.recipes.enrichment.enricher import Acceptance, ConfidenceBar, EnrichmentQuestion, SafeSide

if TYPE_CHECKING:
    from glean.decisions import Decision

__all__ = [
    "DIETARY_ENRICHER",
    "DIETARY_FLAGS",
    "PEANUT_FREE",
    "PEANUT_FREE_THRESHOLD",
    "PREFERENCE_THRESHOLD",
    "THRESHOLDS",
    "TREE_NUT_FREE",
    "TREE_NUT_FREE_THRESHOLD",
    "DietaryEnricher",
    "dietary_enrichment_question",
    "dietary_enrichment_questions",
    "dietary_questions",
]

TREE_NUT_FREE = "tree-nut-free"
PEANUT_FREE = "peanut-free"
# Flags the decision model is asked about. Others (Keto, Paleo) are left to the meal-plan model.
DIETARY_FLAGS = ("vegetarian", "vegan", "dairy-free", "gluten-free", TREE_NUT_FREE, PEANUT_FREE)

# Exclude when the probability that the recipe breaks the flag reaches the threshold.
# Set from the labelled samples (tests/fixtures/decisions/dietary_sample.json, 63 rows, and dietary_regex_coverage.json,
# 182 recipes) answered by typesafe/jev-1.14-20261014 on 2026-10-16 under the criteria below, and checked against all
# 632 prod-corpus recipes. Ground truth there is the retailer's ingredient lists, then the maintainer's labels, then
# two judges and the old regex in agreement:
#   tree-nut-free: 41 recipes break it, every one scored >= 0.95; 1 of 570 clean recipes scores >= 0.3 (0.84)
#   peanut-free:   36 recipes break it, every one scored >= 0.86; 1 of 576 clean recipes scores >= 0.3 (0.44)
# Both thresholds start from the 0.3 the single nut flag used and miss nothing on the corpus; 0.3 sits 0.65 (tree)
# and 0.56 (peanut) below the lowest violator. On the samples tree-nut-free is clean to 0.11 (a bare korma paste);
# peanut-free scores dukkah 0.45, praline 0.35 and a bare chilli crisp 0.33 clean-labelled, which it excludes.
# Only nuts in the ingredients count: a "may contain nuts" warning is ignored, and korma, tikka masala and pasanda
# pastes are not special (a tree nut is listed in 0 of 9 korma and 1 of 7 tikka masala pastes sold).
# Preferences sit between the clusters: 0.12 above the highest clean recipe (gluten-free), 0.27 below the
# lowest violator (gluten-free). 0.50 rather than higher because the gluten-free recipe `rec_d1cddd00fba23e5a`
# of the prod corpus scores 0.52 and must be excluded.
TREE_NUT_FREE_THRESHOLD = 0.3
PEANUT_FREE_THRESHOLD = 0.3
PREFERENCE_THRESHOLD = 0.5
THRESHOLDS = {TREE_NUT_FREE: TREE_NUT_FREE_THRESHOLD, PEANUT_FREE: PEANUT_FREE_THRESHOLD}


# What each question asks, and the household's ingredient policy, given to the model as criteria.
_QUESTIONS: dict[str, NoulQuestion] = {
    "vegetarian": NoulQuestion(
        instructions=(
            "Does this recipe contain meat, poultry, fish, shellfish or another animal-slaughter product? "
            "Caesar dressing (anchovies), Thai curry paste (shrimp paste), fish and oyster sauce and meat stock "
            "all count, as do Worcestershire sauce (anchovies), lard, suet and gelatine. "
            "Parmesan and pesto do not count. Meat-free, vegan and plant-based substitutes are not meat."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains meat, fish, shellfish, gelatine, anchovy or shrimp paste.",
            false="No ingredient is or contains meat, fish or shellfish. Parmesan and pesto are allowed.",
        ),
    ),
    "vegan": NoulQuestion(
        instructions=(
            "Does this recipe contain any animal product? "
            "Naan bread (usually made with yoghurt or milk), pesto (made with cheese), mayonnaise (eggs), honey "
            "and Worcestershire sauce (anchovies) count. Meat-free, vegan and plant-based substitutes, cocoa butter, "
            "peanut and nut butters are not animal products."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains meat, fish, dairy, eggs or honey.",
            false="No ingredient is or contains an animal product. Coconut milk and plant milks are fine.",
        ),
    ),
    "dairy-free": NoulQuestion(
        instructions=(
            "Does this recipe contain dairy? "
            "Whey, buttermilk, ghee, naan bread (usually made with yoghurt or milk) and pesto (made with cheese) "
            "count. "
            "Dairy-free and plant-based substitutes, oat and coconut cream, cocoa butter, peanut and nut butters "
            "are not dairy."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains milk, cheese, butter, cream, yoghurt, whey or buttermilk.",
            false="No ingredient is or contains dairy. Coconut milk and plant milks are fine.",
        ),
    ),
    "gluten-free": NoulQuestion(
        instructions=(
            "Does this recipe contain gluten? Oats count as gluten unless the recipe says gluten-free oats. "
            "Malt vinegar, soy sauce, couscous, barley and rye count, as do gnocchi, wraps, flour tortillas, "
            "noodles and pasta unless labelled gluten-free, and hoisin, teriyaki and kecap manis (made with soy "
            "sauce). Rice, corn (corn tortillas), gram, chickpea, buckwheat, tapioca, potato, coconut and almond "
            "flours are not gluten."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains wheat, barley, rye, malt or oats that aren't gluten-free.",
            false="No ingredient is or contains gluten. Gluten-free oats, rice and cornflour are fine.",
        ),
    ),
    TREE_NUT_FREE: NoulQuestion(
        instructions=(
            "Does this recipe contain tree nuts or anything made from them? "
            "Almonds, cashews, hazelnuts, walnuts, pecans, pistachios, macadamias, Brazil nuts and pine nuts count, "
            "so pesto counts. Marzipan, frangipane, Nutella and other hazelnut spreads, dukkah, romesco, praline "
            "and almond milk count, as does an unspecified nut or nut butter, which may be a tree nut. "
            "A curry paste, seasoning or sauce is not a tree nut unless the name says it has one: assume none is "
            "hidden inside. Peanuts, peanut butter and satay are not tree nuts. "
            "Coconut, coconut milk, nutmeg and seeds are not nuts, and an ingredient labelled nut-free is not a nut."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains a tree nut or pine nut, or a product made from them.",
            false="No ingredient is or contains a tree nut. Peanuts, coconut and nutmeg are not tree nuts.",
        ),
    ),
    PEANUT_FREE: NoulQuestion(
        instructions=(
            "Does this recipe contain peanuts or anything made from them? "
            "Peanut butter, groundnut oil, satay and satay sauce count, as does an unspecified nut "
            "or nut butter, which may be peanut. Tree nuts such as almonds, cashews, walnuts and pine nuts "
            "are not peanuts. Coconut, coconut milk, nutmeg and seeds are not peanuts, and an ingredient "
            "labelled nut-free or peanut-free is not a peanut."
        ),
        criteria=NoulCriteria(
            true="At least one ingredient is or contains peanut or groundnut, or a product made from them.",
            false="No ingredient is or contains peanut. Tree nuts, coconut, coconut milk and nutmeg are not peanuts.",
        ),
    ),
}


def dietary_questions(flags: tuple[str, ...] = DIETARY_FLAGS) -> dict[str, NoulQuestion]:
    """The decision questions the dietary flags ask, by flag. Unchanged wording since the producer (#125)."""
    return {flag: _QUESTIONS[flag] for flag in flags}


def _threshold(flag: str) -> float:
    return THRESHOLDS.get(flag, PREFERENCE_THRESHOLD)


def _accept_noul(name: str) -> Acceptance:
    """Store the probability itself: a dietary question's bar is applied when planning reads the answer."""

    def accept(decision: Decision) -> float:
        return decision.noul(name).noul

    return accept


def _enrichment_question(flag: str) -> EnrichmentQuestion:
    name = dietary_question(flag)
    return EnrichmentQuestion(
        name=name,
        question=_QUESTIONS[flag],
        # A low probability of breaking the flag is the safe answer, so the bar is an exclusion threshold.
        bar=ConfidenceBar(threshold=_threshold(flag), safe_side=SafeSide.LOW),
        accept=_accept_noul(name),
    )


def dietary_enrichment_questions() -> dict[str, EnrichmentQuestion]:
    """Each dietary flag's enrichment question, by flag."""
    return {flag: _enrichment_question(flag) for flag in DIETARY_FLAGS}


def dietary_enrichment_question(flag: str) -> EnrichmentQuestion | None:
    """The enrichment question `flag` asks, or None for a flag the model is not asked about."""
    return _enrichment_question(flag) if flag in _QUESTIONS else None


@dataclass(frozen=True)
class DietaryEnricher:
    """The dietary flags as one enricher: six `noul` questions, one probability each per recipe."""

    name: str = "dietary"
    flags: tuple[str, ...] = DIETARY_FLAGS

    def questions(self) -> tuple[EnrichmentQuestion, ...]:
        return tuple(_enrichment_question(flag) for flag in self.flags)


DIETARY_ENRICHER = DietaryEnricher()
