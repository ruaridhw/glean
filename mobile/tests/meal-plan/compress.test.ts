// mobile/tests/meal-plan/compress.test.ts

import type { PantryItemForCompression } from "@/meal-plan/compress";
import { compressPantry, scorePantryItem } from "@/meal-plan/compress";

const baseItem: PantryItemForCompression = {
  ingredient_id: 1,
  canonical_name: "chicken breast",
  quantity: 400,
  unit: "g",
  expiry_date: null,
  last_used_at: null,
  is_staple: false,
  food_group: "protein",
};

const now = new Date("2026-04-07T12:00:00Z");

describe("scorePantryItem", () => {
  it("scores higher when item expires within 1 day", () => {
    const expiringSoon = { ...baseItem, expiry_date: "2026-04-08" };
    const notExpiring = { ...baseItem, expiry_date: "2026-04-20" };
    expect(scorePantryItem(expiringSoon, now)).toBeGreaterThan(scorePantryItem(notExpiring, now));
  });

  it("scores higher when item has not been used recently", () => {
    const stale = { ...baseItem, last_used_at: "2026-03-07T00:00:00Z" }; // 31 days ago
    const fresh = { ...baseItem, last_used_at: "2026-04-06T00:00:00Z" }; // 1 day ago
    expect(scorePantryItem(stale, now)).toBeGreaterThan(scorePantryItem(fresh, now));
  });

  it("adds 15 points for never-used items", () => {
    const neverUsed = { ...baseItem, last_used_at: null };
    const recentlyUsed = { ...baseItem, last_used_at: "2026-04-06T00:00:00Z" };
    // Never used gets flat 15; recently used gets ~1 day = 1 point
    expect(scorePantryItem(neverUsed, now)).toBeGreaterThan(scorePantryItem(recentlyUsed, now));
  });
});

describe("compressPantry", () => {
  it("excludes staple items", () => {
    const items: PantryItemForCompression[] = [
      { ...baseItem, ingredient_id: 1, is_staple: true },
      { ...baseItem, ingredient_id: 2, canonical_name: "salmon", is_staple: false },
    ];
    const result = compressPantry(items, 15, now);
    expect(result).toHaveLength(1);
    expect(result[0]?.name).toBe("salmon");
  });

  it("excludes zero-quantity items", () => {
    const items: PantryItemForCompression[] = [
      { ...baseItem, ingredient_id: 1, quantity: 0 },
      { ...baseItem, ingredient_id: 2, canonical_name: "salmon", quantity: 200 },
    ];
    const result = compressPantry(items, 15, now);
    expect(result).toHaveLength(1);
    expect(result[0]?.name).toBe("salmon");
  });

  it("returns at most topN items sorted by urgency descending", () => {
    const items: PantryItemForCompression[] = Array.from({ length: 20 }, (_, i) => ({
      ...baseItem,
      ingredient_id: i + 1,
      canonical_name: `ingredient-${i}`,
      expiry_date: i < 5 ? "2026-04-08" : null, // first 5 expire soon
    }));
    const result = compressPantry(items, 10, now);
    expect(result).toHaveLength(10);
    expect(result[0]?.urgency_score).toBeGreaterThanOrEqual(result[9]?.urgency_score ?? 0);
  });

  it("maps ingredient_id to id in the output", () => {
    const items: PantryItemForCompression[] = [{ ...baseItem, ingredient_id: 42 }];
    const result = compressPantry(items, 15, now);
    expect(result[0]?.id).toBe(42);
  });
});
