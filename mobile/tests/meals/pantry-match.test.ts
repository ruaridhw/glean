/** @jest-environment node */
// mobile/tests/meals/pantry-match.test.ts

// Pure-logic test: stub the db layer so importing the module never touches
// expo-sqlite. Only the side-effect-free helpers are exercised here.
jest.mock("@/db/client", () => ({ drizzleDb: {} }));
jest.mock("@/db/schema", () => ({ pantryItems: {}, recipeIngredients: {} }));
jest.mock("drizzle-orm", () => ({ gt: jest.fn(), inArray: jest.fn() }));

import { computePantryMatch, formatPantryMatch } from "@/meals/pantry-match";

describe("computePantryMatch", () => {
  it("counts recipe ingredients present in the pantry set", () => {
    const pantry = new Set([1, 2, 3]);
    expect(computePantryMatch([1, 2, 4, 5], pantry)).toEqual({ n: 2, m: 4 });
  });

  it("returns n=0 when nothing matches", () => {
    expect(computePantryMatch([7, 8], new Set([1, 2]))).toEqual({ n: 0, m: 2 });
  });

  it("counts every ingredient when the pantry covers them all", () => {
    expect(computePantryMatch([1, 2], new Set([1, 2, 3]))).toEqual({ n: 2, m: 2 });
  });

  it("handles a recipe with no ingredients", () => {
    expect(computePantryMatch([], new Set([1]))).toEqual({ n: 0, m: 0 });
  });
});

describe("formatPantryMatch", () => {
  it("formats as 'n of m in pantry'", () => {
    expect(formatPantryMatch({ n: 4, m: 6 })).toBe("4 of 6 in pantry");
  });
});
