"""Canonical nutrition shape shared across recipe layers.

Nutrition data is structurally identical whether it comes from recipe-api.com
(`RecipeApiNutrition`), is persisted in the server-side corpus
(`StoredNutrition`), or is returned to mobile clients (`NutritionOut`). Before
this module existed, the same 7 fields were declared three times, so adding a
nutrition field meant editing every layer by hand with no compiler help
(a classic data-clump / shotgun-surgery smell).

`NutritionFields` is the single canonical shape. Each layer that needs its own
class derives from it instead of restating the fields, and `copy_nutrition`
is the one mapping helper every conversion site uses to move data between
layers.
"""

from __future__ import annotations

from pydantic import BaseModel


class NutritionFields(BaseModel):
    """The 7 canonical nutrition fields, shared by every layer's nutrition model."""

    calories: float = 0
    protein_g: float = 0
    carbohydrates_g: float = 0
    fat_g: float = 0
    fibre_g: float = 0
    sugar_g: float = 0
    sodium_mg: float = 0


def copy_nutrition[T: NutritionFields](source: NutritionFields, target_cls: type[T]) -> T:
    """Map any nutrition-shaped model onto another layer's nutrition model class."""
    return target_cls(**source.model_dump())
