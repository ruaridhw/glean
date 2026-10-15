from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


class Kind(StrEnum):
    INGREDIENT = "ingredient"
    HOUSEHOLD = "household"


class FoodGroup(StrEnum):
    VEGETABLES = "vegetables"
    FRUIT = "fruit"
    PROTEIN = "protein"
    DAIRY = "dairy"
    CARBOHYDRATES = "carbohydrates"
    FATS = "fats"
    CONDIMENTS = "condiments"
    OTHER = "other"

    @property
    def counts_towards_balance(self) -> bool:
        """Whether the meal plan counts this food group when it balances a week. Only "other" does not."""
        return self is not FoodGroup.OTHER


class TrackingMode(StrEnum):
    COUNTED = "counted"
    PRESENCE = "presence"
    PERISHABLE = "perishable"


class StockUnit(StrEnum):
    GRAMS = "g"
    MILLILITRES = "ml"
    COUNT = "count"


class Form(StrEnum):
    FRESH = "fresh"
    FROZEN = "frozen"
    TINNED_JARRED = "tinned_jarred"
    DRIED = "dried"
    NOT_APPLICABLE = "not_applicable"


class GroupId(StrEnum):
    LEAFY_GREENS = "leafy_greens"
    CABBAGE_AND_BROCCOLI = "cabbage_and_broccoli"
    ONIONS_AND_GARLIC = "onions_and_garlic"
    ROOT_VEG = "root_veg"
    TOMATOES_PEPPERS_AND_AUBERGINES = "tomatoes_peppers_and_aubergines"
    BEANS_AND_PULSES = "beans_and_pulses"
    CITRUS = "citrus"
    TROPICAL_FRUIT = "tropical_fruit"
    STONE_FRUIT = "stone_fruit"
    BERRIES = "berries"
    RED_MEAT = "red_meat"
    POULTRY = "poultry"
    FISH_AND_SEAFOOD = "fish_and_seafood"
    EGGS = "eggs"
    DAIRY = "dairy"
    GRAINS = "grains"
    PASTA_AND_RICE = "pasta_and_rice"
    BREAD = "bread"
    OILS_AND_FATS = "oils_and_fats"
    FRESH_HERBS = "fresh_herbs"
    DRIED_HERBS = "dried_herbs"
    SPICES = "spices"
    SAUCES_AND_CONDIMENTS = "sauces_and_condiments"
    BAKING = "baking"
    DRINKS = "drinks"
    SNACKS_AND_TREATS = "snacks_and_treats"
    HOUSEHOLD = "household"
    HEALTH_AND_BEAUTY = "health_and_beauty"
    BABY = "baby"
    PET = "pet"
    OTHER = "other"


_FORMS = (Form.FRESH, Form.FROZEN, Form.TINNED_JARRED, Form.DRIED)
_NOT_APPLICABLE = (Form.NOT_APPLICABLE,)


@dataclass(frozen=True, slots=True)
class GroupRules:
    """The defaults a catalogue item takes from its ingredient group."""

    name: str
    kind: Kind
    food_group: FoodGroup
    tracking_mode: TrackingMode
    # Only counted groups keep a quantity, so only they have a stock unit.
    stock_unit: StockUnit | None
    allowed_forms: tuple[Form, ...]
    # Unopened shelf life in days, per allowed form. Shelf life is never derived from form alone.
    unopened_shelf_life_days: Mapping[Form, int]
    once_opened_shelf_life_days: int | None

    @property
    def has_forms(self) -> bool:
        return self.allowed_forms != _NOT_APPLICABLE


def _with_forms(
    name: str,
    food_group: FoodGroup,
    *,
    fresh: int,
    frozen: int,
    tinned_jarred: int,
    dried: int,
    once_opened: int,
    tracking_mode: TrackingMode = TrackingMode.COUNTED,
) -> GroupRules:
    return GroupRules(
        name=name,
        kind=Kind.INGREDIENT,
        food_group=food_group,
        tracking_mode=tracking_mode,
        stock_unit=StockUnit.GRAMS if tracking_mode is TrackingMode.COUNTED else None,
        allowed_forms=_FORMS,
        unopened_shelf_life_days=MappingProxyType(
            {Form.FRESH: fresh, Form.FROZEN: frozen, Form.TINNED_JARRED: tinned_jarred, Form.DRIED: dried}
        ),
        once_opened_shelf_life_days=once_opened,
    )


def _plain(
    name: str,
    food_group: FoodGroup,
    tracking_mode: TrackingMode,
    *,
    shelf_life: int,
    once_opened: int | None,
    stock_unit: StockUnit | None = None,
    kind: Kind = Kind.INGREDIENT,
) -> GroupRules:
    if tracking_mode is TrackingMode.COUNTED and stock_unit is None:
        raise ValueError(f"{name}: a counted group needs a stock unit")
    return GroupRules(
        name=name,
        kind=kind,
        food_group=food_group,
        tracking_mode=tracking_mode,
        stock_unit=stock_unit if tracking_mode is TrackingMode.COUNTED else None,
        allowed_forms=_NOT_APPLICABLE,
        unopened_shelf_life_days=MappingProxyType({Form.NOT_APPLICABLE: shelf_life}),
        once_opened_shelf_life_days=once_opened,
    )


_C = TrackingMode.COUNTED
_P = TrackingMode.PRESENCE
_PER = TrackingMode.PERISHABLE

GROUPS: Mapping[GroupId, GroupRules] = MappingProxyType(
    {
        GroupId.LEAFY_GREENS: _with_forms(
            "Leafy greens & salad",
            FoodGroup.VEGETABLES,
            fresh=5,
            frozen=365,
            tinned_jarred=730,
            dried=365,
            once_opened=3,
            tracking_mode=_PER,
        ),
        GroupId.CABBAGE_AND_BROCCOLI: _with_forms(
            "Cabbage & broccoli",
            FoodGroup.VEGETABLES,
            fresh=10,
            frozen=365,
            tinned_jarred=730,
            dried=365,
            once_opened=3,
        ),
        GroupId.ONIONS_AND_GARLIC: _with_forms(
            "Onions & garlic", FoodGroup.VEGETABLES, fresh=21, frozen=365, tinned_jarred=730, dried=365, once_opened=5
        ),
        GroupId.ROOT_VEG: _with_forms(
            "Root veg", FoodGroup.VEGETABLES, fresh=21, frozen=365, tinned_jarred=730, dried=365, once_opened=3
        ),
        GroupId.TOMATOES_PEPPERS_AND_AUBERGINES: _with_forms(
            "Tomatoes, peppers & aubergines",
            FoodGroup.VEGETABLES,
            fresh=7,
            frozen=365,
            tinned_jarred=730,
            dried=365,
            once_opened=5,
        ),
        GroupId.BEANS_AND_PULSES: _with_forms(
            "Beans & pulses", FoodGroup.PROTEIN, fresh=5, frozen=365, tinned_jarred=730, dried=730, once_opened=3
        ),
        GroupId.CITRUS: _with_forms(
            "Citrus", FoodGroup.FRUIT, fresh=14, frozen=270, tinned_jarred=730, dried=365, once_opened=3
        ),
        GroupId.TROPICAL_FRUIT: _with_forms(
            "Tropical fruit", FoodGroup.FRUIT, fresh=7, frozen=270, tinned_jarred=730, dried=365, once_opened=3
        ),
        GroupId.STONE_FRUIT: _with_forms(
            "Stone fruit", FoodGroup.FRUIT, fresh=5, frozen=270, tinned_jarred=730, dried=365, once_opened=3
        ),
        GroupId.BERRIES: _with_forms(
            "Berries", FoodGroup.FRUIT, fresh=4, frozen=270, tinned_jarred=730, dried=365, once_opened=3
        ),
        GroupId.RED_MEAT: _with_forms(
            "Red meat", FoodGroup.PROTEIN, fresh=3, frozen=180, tinned_jarred=730, dried=180, once_opened=2
        ),
        GroupId.POULTRY: _with_forms(
            "Poultry", FoodGroup.PROTEIN, fresh=2, frozen=180, tinned_jarred=730, dried=180, once_opened=2
        ),
        GroupId.FISH_AND_SEAFOOD: _with_forms(
            "Fish & seafood", FoodGroup.PROTEIN, fresh=2, frozen=120, tinned_jarred=730, dried=180, once_opened=2
        ),
        GroupId.EGGS: _plain(
            "Eggs", FoodGroup.PROTEIN, _C, shelf_life=21, once_opened=None, stock_unit=StockUnit.COUNT
        ),
        GroupId.DAIRY: _plain("Dairy", FoodGroup.DAIRY, _C, shelf_life=7, once_opened=5, stock_unit=StockUnit.GRAMS),
        GroupId.GRAINS: _plain(
            "Grains", FoodGroup.CARBOHYDRATES, _C, shelf_life=365, once_opened=180, stock_unit=StockUnit.GRAMS
        ),
        GroupId.PASTA_AND_RICE: _plain(
            "Pasta & rice", FoodGroup.CARBOHYDRATES, _C, shelf_life=365, once_opened=365, stock_unit=StockUnit.GRAMS
        ),
        GroupId.BREAD: _plain("Bread", FoodGroup.CARBOHYDRATES, _PER, shelf_life=5, once_opened=None),
        GroupId.OILS_AND_FATS: _plain("Oils & fats", FoodGroup.FATS, _P, shelf_life=365, once_opened=180),
        GroupId.FRESH_HERBS: _plain("Fresh herbs", FoodGroup.CONDIMENTS, _PER, shelf_life=5, once_opened=None),
        GroupId.DRIED_HERBS: _plain("Dried herbs", FoodGroup.CONDIMENTS, _P, shelf_life=365, once_opened=None),
        GroupId.SPICES: _plain("Spices", FoodGroup.CONDIMENTS, _P, shelf_life=365, once_opened=None),
        GroupId.SAUCES_AND_CONDIMENTS: _plain(
            "Sauces & condiments", FoodGroup.CONDIMENTS, _P, shelf_life=365, once_opened=90
        ),
        GroupId.BAKING: _plain("Baking", FoodGroup.CARBOHYDRATES, _P, shelf_life=240, once_opened=None),
        GroupId.DRINKS: _plain(
            "Drinks", FoodGroup.OTHER, _C, shelf_life=365, once_opened=5, stock_unit=StockUnit.MILLILITRES
        ),
        GroupId.SNACKS_AND_TREATS: _plain(
            "Snacks & treats", FoodGroup.OTHER, _C, shelf_life=180, once_opened=14, stock_unit=StockUnit.COUNT
        ),
        GroupId.HOUSEHOLD: _plain(
            "Household",
            FoodGroup.OTHER,
            _C,
            shelf_life=1095,
            once_opened=None,
            stock_unit=StockUnit.COUNT,
            kind=Kind.HOUSEHOLD,
        ),
        GroupId.HEALTH_AND_BEAUTY: _plain(
            "Health & beauty",
            FoodGroup.OTHER,
            _C,
            shelf_life=730,
            once_opened=None,
            stock_unit=StockUnit.COUNT,
            kind=Kind.HOUSEHOLD,
        ),
        GroupId.BABY: _plain(
            "Baby",
            FoodGroup.OTHER,
            _C,
            shelf_life=730,
            once_opened=None,
            stock_unit=StockUnit.COUNT,
            kind=Kind.HOUSEHOLD,
        ),
        GroupId.PET: _plain(
            "Pet",
            FoodGroup.OTHER,
            _C,
            shelf_life=365,
            once_opened=None,
            stock_unit=StockUnit.COUNT,
            kind=Kind.HOUSEHOLD,
        ),
        GroupId.OTHER: _plain(
            "Other", FoodGroup.OTHER, _C, shelf_life=365, once_opened=None, stock_unit=StockUnit.COUNT
        ),
    }
)
