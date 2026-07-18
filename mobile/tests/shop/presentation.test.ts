import {
  formatShoppingItemLabel,
  getShoppingSourceLabel,
  getShoppingSourceTone,
  groupShoppingItems,
} from "@/shop/presentation";
import type { ShoppingListItem } from "@/types";

const item: ShoppingListItem = {
  id: 1,
  ingredient_id: null,
  name: "tomatoes",
  quantity: 2,
  unit: "kg",
  source: "meal_plan",
  is_checked: false,
};

describe("shop presentation", () => {
  it("formats labels and source badges", () => {
    expect(formatShoppingItemLabel(item)).toBe("tomatoes · 2 kg");
    expect(formatShoppingItemLabel({ ...item, quantity: null, unit: null })).toBe("tomatoes");
    expect(getShoppingSourceLabel("manual")).toBe("Manual");
    expect(getShoppingSourceLabel("meal_plan")).toBe("Plan");
    expect(getShoppingSourceLabel("ai")).toBe("AI");
    expect(getShoppingSourceTone("meal_plan")).toBe("primary");
    expect(getShoppingSourceTone("manual")).toBe("neutral");
  });

  it("groups to-buy items before cart items", () => {
    const checked = { ...item, id: 2, name: "milk", is_checked: true };
    const grouped = groupShoppingItems([item, checked]);
    expect(grouped).toEqual([
      { key: "toBuy", title: "To buy", data: [item] },
      { key: "inCart", title: "In your cart", data: [checked] },
    ]);
  });
});
