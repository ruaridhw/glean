/** @jest-environment node */
// mobile/src/__tests__/db/pantry.test.ts

import { getDb } from "@/db/client";
import { updatePantryQuantity, upsertPantryItem } from "@/db/pantry";

jest.mock("@/db/client", () => ({ getDb: jest.fn() }));

describe("upsertPantryItem", () => {
  it("inserts a new row when ingredient not in pantry", async () => {
    const mockDb = {
      getFirstAsync: jest.fn().mockResolvedValue(null),
      runAsync: jest.fn(),
    };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await upsertPantryItem({ ingredient_id: 1, quantity: 500, unit: "g" });

    expect(mockDb.runAsync).toHaveBeenCalledWith(
      expect.stringContaining("INSERT INTO pantry_items"),
      expect.arrayContaining([1, 500, "g"]),
    );
  });

  it("adds to existing quantity when ingredient already in pantry", async () => {
    const mockDb = {
      getFirstAsync: jest.fn().mockResolvedValue({ id: 7, quantity: 200 }),
      runAsync: jest.fn(),
    };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await upsertPantryItem({ ingredient_id: 1, quantity: 300, unit: "g" });

    expect(mockDb.runAsync).toHaveBeenCalledWith(
      expect.stringContaining("UPDATE pantry_items"),
      expect.arrayContaining([300, null, 7]),
    );
  });
});

describe("updatePantryQuantity", () => {
  it("updates quantity for given id", async () => {
    const mockDb = { runAsync: jest.fn() };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await updatePantryQuantity(3, 150);

    expect(mockDb.runAsync).toHaveBeenCalledWith(
      expect.stringContaining("UPDATE pantry_items SET quantity = ?"),
      [150, 3],
    );
  });
});
