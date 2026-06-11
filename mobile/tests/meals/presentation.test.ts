import {
  formatRecipeIngredient,
  getRecipeMeta,
  getRecipeTags,
  parseInstructionSteps,
} from "@/meals/presentation";
import type { Recipe, RecipeIngredient } from "@/types";

const recipe: Recipe = {
  id: 7,
  external_id: "abc",
  title: "Tomato Pasta",
  source_url: "https://example.com",
  cuisine: "Italian",
  difficulty: "easy",
  active_time_mins: 15,
  total_time_mins: 30,
  not_suitable_for: [],
  yield_count: 4,
  nutrition: null,
  instructions: [
    { step_number: 1, phase: "prep", text: "Chop tomatoes" } as never,
    { step_number: 2, phase: "cook", text: "Boil pasta" } as never,
  ],
  last_cooked_at: null,
  is_ai_generated: false,
  dietary_flags: ["Vegetarian"],
};

const ingredient: RecipeIngredient = {
  id: 1,
  recipe_id: 7,
  ingredient_id: 9,
  quantity: 2,
  unit: "whole",
  preparation: "chopped",
  is_optional: false,
  substitutions: [],
  ingredient: {
    id: 9,
    canonical_name: "tomato",
    is_staple: false,
  },
};

describe("meals presentation", () => {
  it("formats recipe metadata from real fields", () => {
    expect(getRecipeMeta(recipe)).toEqual([
      { icon: "time-outline", label: "30 min" },
      { icon: "people-outline", label: "4 servings" },
      { icon: "speedometer-outline", label: "easy" },
    ]);
  });

  it("derives tags without persisted prototype fields", () => {
    expect(getRecipeTags(recipe)).toEqual(["Italian", "Vegetarian", "AI ready"]);
  });

  it("formats ingredients with preparation and optional marker", () => {
    expect(formatRecipeIngredient(ingredient)).toBe("2 whole tomato, chopped");
    expect(formatRecipeIngredient({ ...ingredient, is_optional: true })).toBe(
      "2 whole tomato, chopped (optional)",
    );
  });

  it("formats count ingredients with x notation", () => {
    expect(formatRecipeIngredient({ ...ingredient, quantity: 6, unit: "pcs" })).toBe(
      "6x tomato, chopped",
    );
  });

  it("formats imported canonical units and package context", () => {
    expect(
      formatRecipeIngredient({
        ...ingredient,
        quantity: 800,
        unit: "g",
        preparation: "2 cans",
        ingredient: { id: 10, canonical_name: "Chickpeas", is_staple: false },
      }),
    ).toBe("800g Chickpeas, 2 cans");
    expect(
      formatRecipeIngredient({
        ...ingredient,
        quantity: 2,
        unit: "pcs",
        preparation: null,
        ingredient: { id: 11, canonical_name: "Garlic Clove", is_staple: false },
      }),
    ).toBe("2x Garlic Clove");
    expect(
      formatRecipeIngredient({
        ...ingredient,
        quantity: 240,
        unit: "g",
        preparation: null,
        ingredient: { id: 12, canonical_name: "British Beef Mince", is_staple: false },
      }),
    ).toBe("240g British Beef Mince");
    expect(
      formatRecipeIngredient({
        ...ingredient,
        quantity: 3,
        unit: "cm",
        preparation: null,
        ingredient: { id: 13, canonical_name: "Ginger", is_staple: false },
      }),
    ).toBe("3cm Ginger");
  });

  it("omits empty quantity and unit for pantry basics", () => {
    expect(
      formatRecipeIngredient({
        ...ingredient,
        quantity: 0,
        unit: "",
        preparation: null,
        ingredient: { id: 10, canonical_name: "olive oil", is_staple: false },
      }),
    ).toBe("olive oil");
  });

  it("parses object and string instruction formats", () => {
    expect(parseInstructionSteps(recipe.instructions)).toEqual([
      { number: 1, text: "Chop tomatoes" },
      { number: 2, text: "Boil pasta" },
    ]);
    expect(parseInstructionSteps(["Heat oil", "Serve"])).toEqual([
      { number: 1, text: "Heat oil" },
      { number: 2, text: "Serve" },
    ]);
  });
});
