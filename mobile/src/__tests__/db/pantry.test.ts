/** @jest-environment node */
// mobile/src/__tests__/db/pantry.test.ts

jest.mock("@/db/client", () => ({
  drizzleDb: { select: jest.fn(), insert: jest.fn(), update: jest.fn(), delete: jest.fn() },
}));
jest.mock("drizzle-orm", () => ({
  eq: jest.fn((_col: unknown, val: unknown) => val),
  sql: jest.fn((...args: unknown[]) => args),
  inArray: jest.fn((_col: unknown, vals: unknown) => vals),
}));
jest.mock("@/db/schema", () => ({
  pantryItems: {
    id: "id",
    ingredient_id: "ingredient_id",
    quantity: "quantity",
    unit_price: "unit_price",
    updated_at: "updated_at",
    expiry_date: "expiry_date",
    last_used_at: "last_used_at",
  },
  ingredients: {
    id: "id",
    canonical_name: "canonical_name",
    api_ingredient_id: "api_ingredient_id",
    is_staple: "is_staple",
    category: "category",
  },
  ingredientCategories: { category: "category", food_group: "food_group" },
  shoppingListItems: {},
}));

import { drizzleDb } from "@/db/client";
import { addPantryItem, updatePantryQuantity, upsertPantryItem } from "@/db/pantry";

function makeSelectChain(result: unknown[]) {
  const limit = jest.fn().mockResolvedValue(result);
  const where = jest.fn(() => ({ limit }));
  const from = jest.fn(() => ({ where }));
  return { from };
}

describe("upsertPantryItem", () => {
  beforeEach(() => jest.clearAllMocks());

  it("inserts a new row when ingredient not in pantry", async () => {
    (drizzleDb.select as jest.Mock).mockReturnValue(makeSelectChain([]));
    const mockValues = jest.fn().mockResolvedValue({});
    (drizzleDb.insert as jest.Mock).mockReturnValue({ values: mockValues });

    await upsertPantryItem({ ingredient_id: 1, quantity: 500, unit: "g" });

    expect(drizzleDb.insert).toHaveBeenCalled();
    expect(mockValues).toHaveBeenCalledWith(
      expect.objectContaining({ ingredient_id: 1, quantity: 500, unit: "g" }),
    );
  });

  it("updates quantity when ingredient already in pantry", async () => {
    (drizzleDb.select as jest.Mock).mockReturnValue(makeSelectChain([{ id: 7 }]));
    const mockWhere = jest.fn().mockResolvedValue({});
    const mockSet = jest.fn(() => ({ where: mockWhere }));
    (drizzleDb.update as jest.Mock).mockReturnValue({ set: mockSet });

    await upsertPantryItem({ ingredient_id: 1, quantity: 300, unit: "g" });

    expect(drizzleDb.update).toHaveBeenCalled();
    expect(mockSet).toHaveBeenCalledWith(expect.objectContaining({ quantity: expect.anything() }));
  });
});

describe("addPantryItem", () => {
  beforeEach(() => jest.clearAllMocks());

  it("resolves a new ingredient and inserts a new pantry row", async () => {
    const ingredientRow = { id: 42, canonical_name: "chicken breast", canonical_unit: null };
    (drizzleDb.select as jest.Mock)
      .mockReturnValueOnce(makeSelectChain([])) // findIngredientByName -> not found
      .mockReturnValueOnce(makeSelectChain([])); // upsertPantryItem existing-row check -> not found

    const mockIngredientReturning = jest.fn().mockResolvedValue([ingredientRow]);
    const mockIngredientValues = jest.fn(() => ({ returning: mockIngredientReturning }));
    const mockPantryValues = jest.fn().mockResolvedValue({});
    (drizzleDb.insert as jest.Mock)
      .mockReturnValueOnce({ values: mockIngredientValues })
      .mockReturnValueOnce({ values: mockPantryValues });

    const result = await addPantryItem({ name: "Chicken Breast", quantity: 500, unit: "g" });

    expect(result).toEqual({ ingredientId: 42 });
    expect(mockIngredientValues).toHaveBeenCalledWith(
      expect.objectContaining({ canonical_name: "chicken breast" }),
    );
    expect(mockPantryValues).toHaveBeenCalledWith(
      expect.objectContaining({ ingredient_id: 42, quantity: 500, unit: "g" }),
    );
  });

  it("reuses an existing ingredient and updates an existing pantry row", async () => {
    (drizzleDb.select as jest.Mock)
      .mockReturnValueOnce(
        makeSelectChain([{ id: 7, canonical_name: "rice", canonical_unit: null }]),
      )
      .mockReturnValueOnce(makeSelectChain([{ id: 3 }]));
    const mockWhere = jest.fn().mockResolvedValue({});
    const mockSet = jest.fn(() => ({ where: mockWhere }));
    (drizzleDb.update as jest.Mock).mockReturnValue({ set: mockSet });

    const result = await addPantryItem({ name: "Rice", quantity: 200, unit: "g" });

    expect(result).toEqual({ ingredientId: 7 });
    expect(drizzleDb.insert).not.toHaveBeenCalled();
    expect(drizzleDb.update).toHaveBeenCalled();
    expect(mockSet).toHaveBeenCalledWith(expect.objectContaining({ quantity: expect.anything() }));
  });

  it("normalizes quantity/unit against the ingredient's canonical unit before upserting", async () => {
    (drizzleDb.select as jest.Mock)
      .mockReturnValueOnce(
        makeSelectChain([{ id: 11, canonical_name: "flour", canonical_unit: "g" }]),
      )
      .mockReturnValueOnce(makeSelectChain([]));
    const mockValues = jest.fn().mockResolvedValue({});
    (drizzleDb.insert as jest.Mock).mockReturnValueOnce({ values: mockValues });

    await addPantryItem({ name: "Flour", quantity: 2, unit: "kg" });

    expect(mockValues).toHaveBeenCalledWith(
      expect.objectContaining({ ingredient_id: 11, quantity: 2000, unit: "g" }),
    );
  });
});

describe("updatePantryQuantity", () => {
  beforeEach(() => jest.clearAllMocks());

  it("updates quantity for given id", async () => {
    const mockWhere = jest.fn().mockResolvedValue({});
    const mockSet = jest.fn(() => ({ where: mockWhere }));
    (drizzleDb.update as jest.Mock).mockReturnValue({ set: mockSet });

    await updatePantryQuantity(3, 150);

    expect(drizzleDb.update).toHaveBeenCalled();
    expect(mockSet).toHaveBeenCalledWith(expect.objectContaining({ quantity: 150 }));
  });
});
