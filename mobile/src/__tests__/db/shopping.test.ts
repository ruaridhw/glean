/** @jest-environment node */
// mobile/src/__tests__/db/shopping.test.ts

jest.mock("@/db/client", () => ({
  drizzleDb: { update: jest.fn() },
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

import { drizzleDb } from "@/db/client";
import { checkOffByIngredientIds } from "@/db/shopping";

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
