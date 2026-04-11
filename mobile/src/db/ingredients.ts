// mobile/src/db/ingredients.ts

import { eq } from "drizzle-orm";
import type { Ingredient } from "@/types";
import { drizzleDb } from "./client";
import { ingredients } from "./schema";

async function findIngredientByName(canonicalName: string): Promise<Ingredient | null> {
  const [row] = await drizzleDb
    .select()
    .from(ingredients)
    .where(eq(ingredients.canonical_name, canonicalName.toLowerCase().trim()))
    .limit(1);
  return row ?? null;
}

async function findIngredientByApiId(apiId: string): Promise<Ingredient | null> {
  const [row] = await drizzleDb
    .select()
    .from(ingredients)
    .where(eq(ingredients.api_ingredient_id, apiId))
    .limit(1);
  return row ?? null;
}

export async function getIngredientById(id: number): Promise<Ingredient | null> {
  const [row] = await drizzleDb.select().from(ingredients).where(eq(ingredients.id, id)).limit(1);
  return row ?? null;
}

export async function resolveOrCreateIngredient(params: {
  canonical_name: string;
  api_ingredient_id?: string | null;
  api_name?: string | null;
  category?: string | null;
}): Promise<number> {
  const name = params.canonical_name.toLowerCase().trim();

  if (params.api_ingredient_id) {
    const byId = await findIngredientByApiId(params.api_ingredient_id);
    if (byId) return byId.id;
  }

  const byName = await findIngredientByName(name);
  if (byName) return byName.id;

  const result = await drizzleDb.insert(ingredients).values({
    canonical_name: name,
    api_ingredient_id: params.api_ingredient_id ?? null,
    api_name: params.api_name ?? null,
    category: params.category ?? null,
  });
  return result.lastInsertRowId as number;
}
