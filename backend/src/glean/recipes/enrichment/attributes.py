"""The attribute enricher: what each recipe is made of, how it is shaped, and where it comes from (G1).

Five questions per recipe: a `choice` for `main_protein`, `main_carb`, `dish_type` and `cuisine`, and a
`score` for `whole_food`. Every answer stores the option the model chose and the probability that chose it;
whether that option is *trusted* is decided at read time by the attribute's bar (0.8 by default, tunable per
attribute, never below 0.7). Under the bar the answer reads as `unsure`, which is a real answer — it stops
the recipe being re-asked and earns no variety credit and no penalty — and, because the bar is applied on
read, retuning it takes effect at once instead of waiting for a re-run.

The option sets are `recipes/attributes.py`'s G1 enums, so a stored value is already the value the filter,
the scorer and the check-sample tooling name. The wording lives here because a question's criteria hash is
what its stored answers reply to: editing a criterion re-asks that question and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from glean.decisions import ChoiceQuestion, ScoreQuestion
from glean.recipes.attributes import ATTRIBUTE_QUESTIONS, Cuisine, DishType, MainCarb, MainProtein, WholeFood
from glean.recipes.enrichment.enricher import (
    ATTRIBUTE_BAR_MODEL,
    DEFAULT_ATTRIBUTE_BAR,
    Acceptance,
    EnrichmentQuestion,
    attribute_bar,
    method_state,
    top_choice,
    top_level,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from glean.decisions import Question
    from glean.recipes.stored import StoredRecipe

__all__ = [
    "ATTRIBUTE_ENRICHER",
    "MEASURED_BARS",
    "WHOLE_FOOD_LEVELS",
    "AttributeEnricher",
    "attribute_questions",
    "attribute_questions_by_name",
]

# The whole-food scale's order: lowest level first, which is the order a `score` question's criteria take.
WHOLE_FOOD_LEVELS: tuple[WholeFood, ...] = (WholeFood.PROCESSED, WholeFood.MIXED, WholeFood.WHOLE)

# The bars the 50-recipe check settled (spec 6.1, "Confidence bars"; G1). One sample, split across both import
# sources, labelled by an independent model and adjudicated by the owner only where it and the decision model
# disagreed, so these are provisional and a second sample is what would move them. At these bars that sample
# scored: main_protein 48/48 accepted, 100% right; main_carb 48/48, 100%; dish_type 42/42, 97.6%; cuisine 36/36
# at 0.85, 100%; whole_food 25/25 at 0.90, 96%. dish_type accepts the most at 0.75 (43/43, 97.7%) but 0.80 is
# the spec's starting bar and the extra acceptance was one recipe, so it stays where G1 put it.
#
# A bar is not part of a question's criteria hash, and it is applied when an answer is read, not when it is
# stored: retuning one therefore takes effect on the next read with no re-ask — raising it turns the labels it
# now rejects into `unsure`, lowering it recovers labels stored under the old bar.
MEASURED_BARS: dict[str, float] = {
    "main_protein": 0.80,
    "main_carb": 0.80,
    "dish_type": 0.80,
    "cuisine": 0.85,
    "whole_food": 0.90,
}

_PROTEIN = ChoiceQuestion(
    instructions=(
        "What is the main protein of this dish? Read the title, the ingredients and the method. "
        "Give one value. A dish built around two proteins takes the one it is built around: chicken and "
        "chorizo is chicken, and beef-and-pork mince is beef. Processed meat counts under its animal: bacon, "
        "ham, chorizo, salami and pepperoni are pork. An egg-led or cheese-led dish, such as an omelette, a "
        "frittata or a macaroni cheese, is vegetarian_other. Tofu, tempeh, seitan, Quorn and meat-free "
        "substitutes are tofu_or_plant_protein. Beans, lentils, chickpeas and other pulses are "
        "beans_and_pulses, not none. Use none only when no protein is central to the dish, and mixed only "
        "when two or more proteins carry it equally."
    ),
    criteria={
        MainProtein.CHICKEN.value: (
            "Chicken is the centre: breast, thigh, wings, mince, or a chicken stock it is built on."
        ),
        MainProtein.TURKEY_OR_DUCK.value: "Turkey or duck is the centre, including mince, breast and legs.",
        MainProtein.BEEF.value: "Beef is the centre: steak, mince, brisket, ribs, meatballs.",
        MainProtein.PORK.value: (
            "Pork is the centre, including bacon, ham and pork charcuterie such as chorizo or salami."
        ),
        MainProtein.LAMB.value: "Lamb or mutton is the centre: chops, shoulder, mince, kofta.",
        MainProtein.FISH.value: "Fish is the centre: salmon, cod, tuna, haddock, anchovy or tinned fish.",
        MainProtein.SEAFOOD.value: "Shellfish or molluscs are the centre: prawns, mussels, squid, crab.",
        MainProtein.BEANS_AND_PULSES.value: "Beans, lentils, chickpeas or other pulses are the protein.",
        MainProtein.TOFU_OR_PLANT_PROTEIN.value: (
            "Tofu, tempeh, seitan, Quorn or a meat-free substitute is the protein."
        ),
        MainProtein.VEGETARIAN_OTHER.value: (
            "An egg-led or cheese-led dish, such as an omelette, frittata or macaroni cheese."
        ),
        MainProtein.MIXED.value: (
            "Two or more proteins carry the dish equally, such as a mixed grill or a fish-and-prawn pie."
        ),
        MainProtein.NONE.value: "No protein is central: a side, a sauce, a leaf salad or a plain dessert.",
    },
)

_CARB = ChoiceQuestion(
    instructions=(
        "What is the main carbohydrate of this dish? Give one value. Count the starch the dish is built "
        "around, not a garnish: garlic bread beside a pasta bake is still pasta. A dish served on rice or "
        "with a rice base is rice; a dish rolled in a wrap, a burger in a bun or a sandwich is "
        "bread_or_wraps. Use other_grains for couscous, quinoa, bulgur and polenta, and none when no "
        "carbohydrate is central."
    ),
    criteria={
        MainCarb.RICE.value: "Rice is the base or the accompaniment the dish is built around.",
        MainCarb.PASTA.value: "Pasta, including spaghetti, penne, lasagne sheets, gnocchi and orzo.",
        MainCarb.NOODLES.value: "Noodles: egg, rice, udon, soba, vermicelli, instant.",
        MainCarb.POTATO.value: "Potato: boiled, roasted, mashed, chipped or in a potato salad.",
        MainCarb.BREAD_OR_WRAPS.value: "Bread, buns, wraps, tortillas, pittas, tacos, sandwiches and toast.",
        MainCarb.OTHER_GRAINS.value: "Couscous, quinoa, bulgur, polenta, barley, freekeh or another grain.",
        MainCarb.NONE.value: "No carbohydrate is central: a soup, a salad, a protein with vegetables.",
    },
)

_DISH_TYPE = ChoiceQuestion(
    instructions=(
        "What shape of dish is this? Give one value, choosing the closest. A spiced dish with a sauce is a "
        "curry even when it is cooked in one pan; a thick dish of vegetables and pulses simmered in liquid "
        "is soup_or_stew rather than curry; anything with the starch and protein tossed together over high "
        "heat is stir_fry; rice cooked into the dish itself is rice_dish. Use other when none of the shapes "
        "fit."
    ),
    criteria={
        DishType.CURRY.value: "A spiced dish with a sauce, served with rice or bread.",
        DishType.STIR_FRY.value: (
            "Ingredients tossed over high heat in a wok or wide pan, usually with noodles or rice."
        ),
        DishType.PASTA_DISH.value: "Pasta as the body of the dish, with a sauce, a bake or a toss.",
        DishType.SOUP_OR_STEW.value: "A liquid-led dish, simmered: soup, stew, chilli, casserole, dal.",
        DishType.ROAST_OR_TRAYBAKE.value: "Everything roasted together on a tray, or a joint roasted whole.",
        DishType.SALAD_OR_BOWL.value: (
            "Served cold or warm as a salad or a grain bowl, assembled rather than cooked together."
        ),
        DishType.HANDHELD.value: "Eaten in the hand: burgers, wraps, tacos, sandwiches, pittas, flatbreads.",
        DishType.PIE_OR_BAKE.value: "A pastry case, a crumble, a gratin or a layered oven bake.",
        DishType.RICE_DISH.value: "Rice cooked into the dish: risotto, pilaf, paella, fried rice, biryani.",
        DishType.PAN_OR_GRILL.value: "A protein or vegetable cooked in a pan or on a grill and served with its sides.",
        DishType.OTHER.value: "None of these shapes: a dessert, a drink, a sauce, a breakfast.",
    },
)

_CUISINE = ChoiceQuestion(
    instructions=(
        "Which regional cuisine is this dish? Give one value. Judge from the title, the ingredients, the "
        "spices and the method. A dish the source calls '<cuisine>-Inspired' takes that cuisine. There is no "
        "fusion value: a dish that genuinely mixes two traditions, with no dominant one, is other. Use other "
        "also for a cuisine this list does not name. Use British for the everyday British repertoire "
        "(roasts, pies, fish and chips, shepherd's pie) rather than for a dish adopted from elsewhere."
    ),
    criteria={
        Cuisine.BRITISH.value: "British and Irish home cooking: roasts, pies, stews, fish and chips, puddings.",
        Cuisine.ITALIAN.value: "Italian: pasta, risotto, pizza and Italian-inspired bakes and sauces.",
        Cuisine.FRENCH.value: "French: bistro dishes, gratins, sauces, quiches, Provençal cooking.",
        Cuisine.SPANISH.value: "Spanish: tapas, paella, chorizo-led dishes, patatas bravas.",
        Cuisine.GREEK.value: "Greek and Cypriot: souvlaki, moussaka, halloumi, Greek salads.",
        Cuisine.MIDDLE_EASTERN.value: (
            "Middle Eastern: Levantine, Turkish, Persian and Israeli cooking, mezze, tagines."
        ),
        Cuisine.NORTH_AFRICAN.value: (
            "North African: Moroccan, Tunisian, Algerian and Egyptian cooking, harissa, couscous."
        ),
        Cuisine.INDIAN.value: "Indian and Pakistani: curries, dal, biryani, dosa, tandoori dishes.",
        Cuisine.THAI.value: "Thai: curries, stir-fries, salads and soups with fish sauce, lime and chilli.",
        Cuisine.VIETNAMESE.value: "Vietnamese: pho, banh mi, fresh rolls, caramel-braised dishes.",
        Cuisine.CHINESE.value: "Chinese: stir-fries, braises, dumplings, Sichuan and Cantonese dishes.",
        Cuisine.JAPANESE.value: "Japanese: sushi, ramen, donburi, teriyaki, katsu.",
        Cuisine.KOREAN.value: "Korean: kimchi and gochujang-led dishes, bibimbap, bulgogi.",
        Cuisine.SOUTHEAST_ASIAN.value: "Southeast Asian outside Thailand and Vietnam: Indonesian, Malaysian, Filipino.",
        Cuisine.MEXICAN.value: "Mexican: tacos, enchiladas, salsas, beans and corn-led dishes.",
        Cuisine.CARIBBEAN.value: "Caribbean: Jamaican and Trinidadian cooking, jerk, rice and peas, curries.",
        Cuisine.AMERICAN.value: "American: burgers, barbecue, mac and cheese, Southern and diner dishes.",
        Cuisine.LATIN_AMERICAN.value: "Latin American outside Mexico: Peruvian, Brazilian, Argentinian, Colombian.",
        Cuisine.OTHER.value: "A regional cuisine this list does not name, or a dish that genuinely mixes traditions.",
    },
)

_WHOLE_FOOD = ScoreQuestion(
    instructions=(
        "How much of this dish is cooked from unprocessed ingredients? Judge by the ingredients, not by the "
        "effort or the length of the method: a long recipe built on a jar of sauce is mixed, and a quick one "
        "of fresh vegetables, pulses and rice is whole. A single shortcut in an otherwise from-scratch dish "
        "is mixed, not processed."
    ),
    criteria=[
        # Lowest level first: a `score` question orders its criteria from the bottom of the scale.
        "Built around ready-made products: a jar of sauce, ready-made pastry, a packet mix, a breaded frozen product.",
        "Mostly cooked from scratch with a shortcut or two: a stock cube, a jar of paste, a tin of soup.",
        "Cooked from unprocessed ingredients: meat, fish, vegetables, pulses, grains, spices and oil.",
    ],
)

# The attributes this family asks about. Active time has its own enricher, so it is not here even though
# the contract's `ATTRIBUTE_QUESTIONS` maps its projection key to its question name too.
_ASKED: tuple[str, ...] = ("main_protein", "main_carb", "dish_type", "cuisine", "whole_food")

_QUESTIONS: dict[str, Question] = {
    "main_protein": _PROTEIN,
    "main_carb": _CARB,
    "dish_type": _DISH_TYPE,
    "cuisine": _CUISINE,
    "whole_food": _WHOLE_FOOD,
}


@dataclass(frozen=True)
class AttributeEnricher:
    """The five G1 attribute questions, one per recipe, each with its own bar.

    `bars` maps an attribute name (`main_protein`, `cuisine`, ...) to a threshold that overrides the one the
    check sample measured (`MEASURED_BARS`), which is what ships. Every threshold goes through
    `attribute_bar`, so a looser-than-allowed bar is a declaration error rather than a quietly weaker answer.
    """

    name: str = "attributes"
    bars: Mapping[str, float] = field(default_factory=dict)

    def questions(self) -> tuple[EnrichmentQuestion, ...]:
        return tuple(self.question_for(attribute) for attribute in _ASKED)

    def state(self, recipe: StoredRecipe | None) -> Mapping[str, object]:
        """The method, which the whole-food judgement needs and the other four benefit from."""
        return method_state(recipe)

    def threshold(self, attribute: str) -> float:
        """The attribute's measured bar, unless a caller overrides it for one run."""
        return self.bars.get(attribute, MEASURED_BARS.get(attribute, DEFAULT_ATTRIBUTE_BAR))

    def question_for(self, attribute: str) -> EnrichmentQuestion:
        """The question for one attribute, with its bar and the rule that stores the model's answer."""
        bar = attribute_bar(self.threshold(attribute))
        name = ATTRIBUTE_QUESTIONS[attribute]
        acceptance: Acceptance = (
            top_level(name, [level.value for level in WHOLE_FOOD_LEVELS])
            if attribute == "whole_food"
            else top_choice(name)
        )
        return EnrichmentQuestion(
            name=name, question=_QUESTIONS[attribute], bar=bar, accept=acceptance, model=ATTRIBUTE_BAR_MODEL
        )


ATTRIBUTE_ENRICHER = AttributeEnricher()


def attribute_questions(bars: Mapping[str, float] | None = None) -> dict[str, EnrichmentQuestion]:
    """The attribute questions by attribute name, for the read side, the tooling and the tests."""
    enricher = ATTRIBUTE_ENRICHER if bars is None else AttributeEnricher(bars=bars)
    return {attribute: enricher.question_for(attribute) for attribute in _ASKED}


def attribute_questions_by_name(
    bars: Mapping[str, float] | None = None,
) -> dict[str, EnrichmentQuestion]:
    """The same questions keyed by their stored question name, which is the key an answer carries.

    `attributes_from_answers` reads a mapping keyed this way, so a caller that changes a bar (the check tool,
    a test) passes this rather than the attribute-keyed view.
    """
    return {question.name: question for question in attribute_questions(bars).values()}
