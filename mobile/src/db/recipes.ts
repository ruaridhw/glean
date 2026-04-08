import { desc, eq } from "drizzle-orm";
import type { Recipe, RecipeIngredient } from "@/types";
import { drizzleDb } from "./client";
import { ingredientCategories, ingredients, recipeDietaryFlags, recipeIngredients, recipes } from "./schema";
import { resolveOrCreateIngredient } from "./ingredients";

function parseRecipe(row: typeof recipes.$inferSelect): Recipe {
  return {
    ...row,
    not_suitable_for: JSON.parse(row.not_suitable_for ?? "[]"),
    instructions: JSON.parse(row.instructions ?? "[]"),
  };
}

export async function getSavedRecipes(): Promise<Recipe[]> {
  const rows = await drizzleDb.select().from(recipes).orderBy(desc(recipes.id));
  return rows.map(parseRecipe);
}

export async function getRecipeById(id: number): Promise<Recipe | null> {
  const [row] = await drizzleDb.select().from(recipes).where(eq(recipes.id, id)).limit(1);
  return row ? parseRecipe(row) : null;
}

export async function getRecipeByExternalId(externalId: string): Promise<Recipe | null> {
  const [row] = await drizzleDb
    .select()
    .from(recipes)
    .where(eq(recipes.external_id, externalId))
    .limit(1);
  return row ? parseRecipe(row) : null;
}

export interface SaveRecipeParams {
  external_id?: string | null;
  title: string;
  source_url?: string | null;
  cuisine?: string | null;
  difficulty?: string | null;
  active_time_mins?: number | null;
  total_time_mins?: number | null;
  dietary_flags?: string[];
  not_suitable_for?: string[];
  yield_count?: number | null;
  nutrition?: object | null;
  instructions?: Array<{ step_number: number; phase: string; text: string }>;
  is_ai_generated?: boolean;
  ingredients: Array<{
    api_ingredient_id?: string | null;
    canonical_name: string;
    quantity: number;
    unit: string;
    preparation?: string | null;
    is_optional?: boolean;
    substitutions?: string[];
  }>;
}

export async function saveRecipe(params: SaveRecipeParams): Promise<number> {
  const result = await drizzleDb.insert(recipes).values({
    external_id: params.external_id ?? null,
    title: params.title,
    source_url: params.source_url ?? null,
    cuisine: params.cuisine ?? null,
    difficulty: params.difficulty ?? null,
    active_time_mins: params.active_time_mins ?? null,
    total_time_mins: params.total_time_mins ?? null,
    not_suitable_for: JSON.stringify(params.not_suitable_for ?? []),
    yield_count: params.yield_count ?? null,
    nutrition: params.nutrition ? JSON.stringify(params.nutrition) : null,
    instructions: JSON.stringify(params.instructions ?? []),
    is_ai_generated: params.is_ai_generated ?? false,
  });

  const recipeId = result.lastInsertRowId as number;

  for (const flag of params.dietary_flags ?? []) {
    await drizzleDb
      .insert(recipeDietaryFlags)
      .values({ recipe_id: recipeId, flag })
      .onConflictDoNothing();
  }

  for (const ing of params.ingredients) {
    const ingredientId = await resolveOrCreateIngredient({
      canonical_name: ing.canonical_name,
      api_ingredient_id: ing.api_ingredient_id ?? null,
    });
    await drizzleDb.insert(recipeIngredients).values({
      recipe_id: recipeId,
      ingredient_id: ingredientId,
      quantity: ing.quantity,
      unit: ing.unit,
      preparation: ing.preparation ?? null,
      is_optional: ing.is_optional ?? false,
      substitutions: JSON.stringify(ing.substitutions ?? []),
    });
  }

  return recipeId;
}

export async function getRecipeIngredients(recipeId: number): Promise<RecipeIngredient[]> {
  const rows = await drizzleDb
    .select({
      id: recipeIngredients.id,
      recipe_id: recipeIngredients.recipe_id,
      ingredient_id: recipeIngredients.ingredient_id,
      quantity: recipeIngredients.quantity,
      unit: recipeIngredients.unit,
      preparation: recipeIngredients.preparation,
      is_optional: recipeIngredients.is_optional,
      substitutions: recipeIngredients.substitutions,
      canonical_name: ingredients.canonical_name,
      api_ingredient_id: ingredients.api_ingredient_id,
      api_name: ingredients.api_name,
      category: ingredients.category,
      canonical_unit: ingredients.canonical_unit,
      is_staple: ingredients.is_staple,
    })
    .from(recipeIngredients)
    .innerJoin(ingredients, eq(recipeIngredients.ingredient_id, ingredients.id))
    .where(eq(recipeIngredients.recipe_id, recipeId));

  return rows.map((r) => ({
    id: r.id,
    recipe_id: r.recipe_id,
    ingredient_id: r.ingredient_id,
    quantity: r.quantity,
    unit: r.unit,
    preparation: r.preparation,
    is_optional: r.is_optional,
    substitutions: JSON.parse(r.substitutions ?? "[]"),
    ingredient: {
      id: r.ingredient_id,
      canonical_name: r.canonical_name,
      api_ingredient_id: r.api_ingredient_id,
      api_name: r.api_name,
      category: r.category,
      canonical_unit: r.canonical_unit,
      is_staple: r.is_staple,
    },
  }));
}
