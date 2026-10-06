// mobile/src/meal-plan/apply.ts

import { apiClient } from "@/api/client";
import type { MealPlanSuggestion, RecipeOut } from "@/api/types";
import { addMealPlanEntry } from "@/db/plan";
import { getRecipeByExternalId, saveRecipe } from "@/db/recipes";
import { addShoppingGapsForRecipe } from "@/db/shopping";

// Adds generated suggestions to the plan, saving corpus recipes locally first
// (a plan entry must point at a saved recipe). Returns how many were planned;
// a suggestion whose recipe can't be fetched is skipped rather than failing the rest.
export async function planSuggestions(suggestions: MealPlanSuggestion[]): Promise<number> {
  let planned = 0;
  for (const suggestion of suggestions) {
    const recipeId = await resolveRecipeId(suggestion);
    if (recipeId == null) continue;
    await addMealPlanEntry(recipeId);
    await addShoppingGapsForRecipe(recipeId);
    planned += 1;
  }
  return planned;
}

async function resolveRecipeId(suggestion: MealPlanSuggestion): Promise<number | null> {
  if (!suggestion.external_id) return suggestion.recipe_id ?? null;
  const saved = await getRecipeByExternalId(suggestion.external_id);
  if (saved) return saved.id;
  try {
    const detail = await apiClient.get<RecipeOut>(`/recipes/${suggestion.external_id}`);
    return await saveRecipe({ ...detail, ingredients: detail.ingredients ?? [] });
  } catch {
    return null;
  }
}
