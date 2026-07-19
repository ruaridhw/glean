/** @jest-environment node */
// mobile/src/__tests__/db/ingredients.test.ts

jest.mock("@/db/client", () => ({
  drizzleDb: { select: jest.fn(), insert: jest.fn() },
}));
jest.mock("drizzle-orm", () => ({
  eq: jest.fn((_col: unknown, val: unknown) => val),
  sql: jest.fn((...args: unknown[]) => args),
  inArray: jest.fn((_col: unknown, vals: unknown) => vals),
}));
jest.mock("@/db/schema", () => ({
  ingredients: {
    id: "id",
    canonical_name: "canonical_name",
    api_ingredient_id: "api_ingredient_id",
  },
  pantryItems: {},
  ingredientCategories: {},
  shoppingListItems: {},
}));

import { drizzleDb } from "@/db/client";
import { resolveOrCreateIngredient } from "@/db/ingredients";

function makeSelectChain(result: unknown[]) {
  const limit = jest.fn().mockResolvedValue(result);
  const where = jest.fn(() => ({ limit }));
  const from = jest.fn(() => ({ where }));
  return { from };
}

describe("resolveOrCreateIngredient", () => {
  beforeEach(() => jest.clearAllMocks());

  it("returns existing row when ingredient found by api_ingredient_id", async () => {
    (drizzleDb.select as jest.Mock).mockReturnValue(
      makeSelectChain([{ id: 5, canonical_name: "chicken breast" }]),
    );

    const ingredient = await resolveOrCreateIngredient({
      canonical_name: "Chicken Breast",
      api_ingredient_id: "uuid-123",
    });

    expect(ingredient).toEqual({ id: 5, canonical_name: "chicken breast" });
    expect(drizzleDb.insert).not.toHaveBeenCalled();
  });

  it("normalises name to lowercase and inserts when not found", async () => {
    (drizzleDb.select as jest.Mock).mockReturnValue(makeSelectChain([]));
    const mockReturning = jest.fn().mockResolvedValue([{ id: 9, canonical_name: "salmon fillet" }]);
    const mockValues = jest.fn(() => ({ returning: mockReturning }));
    (drizzleDb.insert as jest.Mock).mockReturnValue({ values: mockValues });

    const ingredient = await resolveOrCreateIngredient({ canonical_name: "Salmon Fillet" });

    expect(ingredient).toEqual({ id: 9, canonical_name: "salmon fillet" });
    expect(mockValues).toHaveBeenCalledWith(
      expect.objectContaining({ canonical_name: "salmon fillet" }),
    );
  });
});
