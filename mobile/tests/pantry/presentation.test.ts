import type { PantryItem } from "@/types";
import {
  formatPantryQuantity,
  getExpiryBadge,
  getPantryCategoryMeta,
  groupPantryItems,
} from "@/pantry/presentation";

const baseItem: PantryItem = {
  id: 1,
  ingredient_id: 10,
  quantity: 2,
  unit: "kg",
  unit_price: null,
  expiry_date: null,
  last_used_at: null,
  updated_at: "2026-05-02T00:00:00Z",
  canonical_name: "broccoli",
  is_staple: false,
  food_group: "vegetables",
};

describe("pantry presentation", () => {
  it("maps known food groups to display metadata", () => {
    expect(getPantryCategoryMeta("vegetables")).toEqual({
      key: "vegetables",
      label: "Veg & Fruit",
      color: "#4CAF50",
      icon: "leaf-outline",
    });
  });

  it("falls back unknown groups to other", () => {
    expect(getPantryCategoryMeta(null)).toEqual({
      key: "other",
      label: "Other",
      color: "#64748B",
      icon: "cube-outline",
    });
  });

  it("formats quantities with a space between number and unit", () => {
    expect(formatPantryQuantity({ ...baseItem, quantity: 1.5, unit: "kg" })).toBe("1.5 kg");
    expect(formatPantryQuantity({ ...baseItem, quantity: 2, unit: "whole" })).toBe("2 whole");
  });

  it("groups pantry items by display category", () => {
    const grouped = groupPantryItems([
      baseItem,
      { ...baseItem, id: 2, canonical_name: "milk", food_group: "dairy" },
    ]);

    expect(grouped.map((section) => section.title)).toEqual(["Veg & Fruit", "Dairy"]);
    expect(grouped[0]!.items[0]!.canonical_name).toBe("broccoli");
  });

  it("returns expiry badge labels relative to a supplied date", () => {
    const today = new Date("2026-05-02T12:00:00Z");
    expect(getExpiryBadge("2026-05-01", today)).toEqual({ label: "Expired", tone: "expired" });
    expect(getExpiryBadge("2026-05-02", today)).toEqual({ label: "Today", tone: "expired" });
    expect(getExpiryBadge("2026-05-04", today)).toEqual({ label: "2d left", tone: "soon" });
    expect(getExpiryBadge("2026-05-07", today)).toEqual({ label: "5d left", tone: "later" });
    expect(getExpiryBadge(null, today)).toBeNull();
  });
});
