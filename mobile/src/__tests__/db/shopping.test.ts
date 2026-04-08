/** @jest-environment node */
// mobile/src/__tests__/db/shopping.test.ts

import { getDb } from "@/db/client";
import { checkOffByIngredientIds } from "@/db/shopping";

jest.mock("@/db/client", () => ({ getDb: jest.fn() }));

describe("checkOffByIngredientIds", () => {
  it("marks matching shopping list items as checked", async () => {
    const mockDb = { runAsync: jest.fn() };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await checkOffByIngredientIds([1, 3, 5]);

    expect(mockDb.runAsync).toHaveBeenCalledWith(
      expect.stringContaining("UPDATE shopping_list_items SET is_checked = 1"),
      [1, 3, 5],
    );
  });

  it("does nothing when passed empty array", async () => {
    const mockDb = { runAsync: jest.fn() };
    (getDb as jest.Mock).mockResolvedValue(mockDb);

    await checkOffByIngredientIds([]);

    expect(mockDb.runAsync).not.toHaveBeenCalled();
  });
});
