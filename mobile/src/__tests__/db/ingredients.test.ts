/** @jest-environment node */
// mobile/src/__tests__/db/ingredients.test.ts

import { getDb } from "@/db/client";
import { resolveOrCreateIngredient } from "@/db/ingredients";

jest.mock("@/db/client", () => ({ getDb: jest.fn() }));

describe("resolveOrCreateIngredient", () => {
  it("returns existing id when ingredient found by api_ingredient_id", async () => {
    const mockDb = {
      getFirstAsync: jest.fn().mockResolvedValueOnce({ id: 5, canonical_name: "chicken breast" }),
      runAsync: jest.fn(),
    };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    const id = await resolveOrCreateIngredient({
      canonical_name: "Chicken Breast",
      api_ingredient_id: "uuid-123",
    });

    expect(id).toBe(5);
    expect(mockDb.runAsync).not.toHaveBeenCalled();
  });

  it("normalises name to lowercase and inserts when not found", async () => {
    const mockDb = {
      getFirstAsync: jest.fn().mockResolvedValue(null),
      runAsync: jest.fn().mockResolvedValue({ lastInsertRowId: 9 }),
    };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    const id = await resolveOrCreateIngredient({ canonical_name: "Salmon Fillet" });

    expect(id).toBe(9);
    expect(mockDb.runAsync).toHaveBeenCalledWith(
      expect.stringContaining("INSERT INTO ingredients"),
      expect.arrayContaining(["salmon fillet"]),
    );
  });
});
