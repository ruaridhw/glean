/** @jest-environment node */
// mobile/src/__tests__/db/shopping.test.ts

jest.mock("@/db/client", () => ({
  drizzleDb: { insert: jest.fn(), update: jest.fn() },
}));
jest.mock("drizzle-orm", () => ({
  eq: jest.fn((_col: unknown, val: unknown) => val),
  sql: jest.fn((...args: unknown[]) => args),
  inArray: jest.fn((_col: unknown, vals: unknown) => vals),
}));
jest.mock("@/db/schema", () => ({
  shoppingListItems: { ingredient_id: "ingredient_id", is_checked: "is_checked" },
  pantryItems: {},
  ingredients: {},
  ingredientCategories: {},
}));
const mockResolveOrCreateIngredient = jest.fn();
jest.mock("@/db/ingredients", () => ({
  resolveOrCreateIngredient: (...args: unknown[]) => mockResolveOrCreateIngredient(...args),
}));

import { drizzleDb } from "@/db/client";
import { addAiShoppingItems, checkOffByIngredientIds } from "@/db/shopping";

describe("checkOffByIngredientIds", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    const mockWhere = jest.fn().mockResolvedValue({});
    const mockSet = jest.fn(() => ({ where: mockWhere }));
    (drizzleDb.update as jest.Mock).mockReturnValue({ set: mockSet });
  });

  it("marks matching shopping list items as checked", async () => {
    await checkOffByIngredientIds([1, 3, 5]);

    expect(drizzleDb.update).toHaveBeenCalled();
    const mockSet = (drizzleDb.update as jest.Mock).mock.results[0]!.value.set as jest.Mock;
    expect(mockSet).toHaveBeenCalledWith({ is_checked: true });
  });

  it("does nothing when passed empty array", async () => {
    await checkOffByIngredientIds([]);
    expect(drizzleDb.update).not.toHaveBeenCalled();
  });
});

describe("addAiShoppingItems", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("resolves accepted AI proposals and inserts them with source ai", async () => {
    const mockValues = jest.fn().mockResolvedValue({});
    const mockInsert = jest.fn(() => ({ values: mockValues }));
    (drizzleDb as unknown as { insert: jest.Mock }).insert = mockInsert;
    mockResolveOrCreateIngredient.mockResolvedValueOnce(101).mockResolvedValueOnce(102);

    await addAiShoppingItems([
      {
        name: "taco shells",
        quantity: 1,
        unit: "pack",
        api_ingredient_id: "taco-shells",
        category: "bakery",
      },
      {
        name: "whole milk",
        quantity: 1,
        unit: "bottle",
        api_ingredient_id: null,
        category: "dairy",
      },
    ]);

    expect(mockResolveOrCreateIngredient).toHaveBeenNthCalledWith(1, {
      canonical_name: "taco shells",
      api_ingredient_id: "taco-shells",
      category: "bakery",
    });
    expect(mockResolveOrCreateIngredient).toHaveBeenNthCalledWith(2, {
      canonical_name: "whole milk",
      api_ingredient_id: null,
      category: "dairy",
    });
    expect(mockInsert).toHaveBeenCalled();
    expect(mockValues).toHaveBeenCalledWith([
      {
        ingredient_id: 101,
        name: "taco shells",
        quantity: 1,
        unit: "pack",
        source: "ai",
      },
      {
        ingredient_id: 102,
        name: "whole milk",
        quantity: 1,
        unit: "bottle",
        source: "ai",
      },
    ]);
  });

  it("does nothing when there are no accepted proposals", async () => {
    const mockInsert = jest.fn();
    (drizzleDb as unknown as { insert: jest.Mock }).insert = mockInsert;

    await addAiShoppingItems([]);

    expect(mockInsert).not.toHaveBeenCalled();
    expect(mockResolveOrCreateIngredient).not.toHaveBeenCalled();
  });
});
