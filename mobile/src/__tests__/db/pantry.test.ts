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
    is_staple: "is_staple",
    category: "category",
  },
  ingredientCategories: { category: "category", food_group: "food_group" },
  shoppingListItems: {},
}));

import { drizzleDb } from "@/db/client";
import { updatePantryQuantity, upsertPantryItem } from "@/db/pantry";

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
