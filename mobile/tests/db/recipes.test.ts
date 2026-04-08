/** @jest-environment node */
// mobile/tests/db/recipes.test.ts

jest.mock("@/db/client", () => ({
  drizzleDb: { select: jest.fn(), insert: jest.fn() },
}));
jest.mock("drizzle-orm", () => ({
  eq: jest.fn((_col: unknown, val: unknown) => val),
  desc: jest.fn((col: unknown) => col),
}));
jest.mock("@/db/schema", () => ({
  recipes: {
    id: "id",
    external_id: "external_id",
    title: "title",
  },
  recipeDietaryFlags: { recipe_id: "recipe_id", flag: "flag" },
  recipeIngredients: {
    recipe_id: "recipe_id",
    ingredient_id: "ingredient_id",
    quantity: "quantity",
    unit: "unit",
    preparation: "preparation",
    is_optional: "is_optional",
    substitutions: "substitutions",
  },
  ingredients: { id: "id", canonical_name: "canonical_name" },
  ingredientCategories: {},
}));
jest.mock("@/db/ingredients", () => ({
  resolveOrCreateIngredient: jest.fn(),
}));

import { drizzleDb } from "@/db/client";
import { resolveOrCreateIngredient } from "@/db/ingredients";
import { saveRecipe } from "@/db/recipes";

describe("saveRecipe", () => {
  beforeEach(() => jest.clearAllMocks());

  it("inserts recipe and its ingredients, returns new id", async () => {
    let callCount = 0;
    (drizzleDb.insert as jest.Mock).mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        // recipe insert → needs to return lastInsertRowId
        return { values: jest.fn().mockResolvedValue({ lastInsertRowId: 42 }) };
      }
      // ingredient insert
      return { values: jest.fn().mockResolvedValue({}) };
    });
    (resolveOrCreateIngredient as jest.Mock).mockResolvedValue(1);

    const id = await saveRecipe({
      title: "Pasta",
      ingredients: [{ canonical_name: "spaghetti", quantity: 200, unit: "g" }],
    });

    expect(id).toBe(42);
    expect(drizzleDb.insert).toHaveBeenCalledTimes(2); // recipe + 1 ingredient
  });

  it("inserts each dietary flag into recipe_dietary_flags", async () => {
    let callCount = 0;
    (drizzleDb.insert as jest.Mock).mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return { values: jest.fn().mockResolvedValue({ lastInsertRowId: 1 }) };
      }
      return {
        values: jest.fn().mockReturnValue({ onConflictDoNothing: jest.fn().mockResolvedValue({}) }),
      };
    });
    (resolveOrCreateIngredient as jest.Mock).mockResolvedValue(1);

    await saveRecipe({
      title: "GF Pasta",
      dietary_flags: ["Gluten-Free", "Vegan"],
      ingredients: [{ canonical_name: "rice pasta", quantity: 200, unit: "g" }],
    });

    // 1 recipe + 2 flags + 1 ingredient = 4 inserts
    expect(drizzleDb.insert).toHaveBeenCalledTimes(4);
  });

  it("does not include dietary_flags in the recipe row values", async () => {
    let recipeValues: Record<string, unknown> | null = null;
    let callCount = 0;
    (drizzleDb.insert as jest.Mock).mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return {
          values: jest.fn().mockImplementation((v: Record<string, unknown>) => {
            recipeValues = v;
            return Promise.resolve({ lastInsertRowId: 1 });
          }),
        };
      }
      return {
        values: jest.fn().mockReturnValue({ onConflictDoNothing: jest.fn().mockResolvedValue({}) }),
      };
    });
    (resolveOrCreateIngredient as jest.Mock).mockResolvedValue(1);

    await saveRecipe({
      title: "GF Pasta",
      dietary_flags: ["Gluten-Free"],
      ingredients: [{ canonical_name: "rice pasta", quantity: 200, unit: "g" }],
    });

    expect(recipeValues).not.toBeNull();
    expect(recipeValues).not.toHaveProperty("dietary_flags");
    expect(recipeValues).toHaveProperty("title", "GF Pasta");
  });
});
