import type { Recipe, RecipeIngredient } from "@/types";
import {
  formatRecipeIngredient,
  getRecipeMeta,
  getRecipeTags,
  parseInstructionSteps,
} from "@/meals/presentation";

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
