import {
  formatShoppingQuantity,
  getShoppingSourceLabel,
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
  it("formats quantities and source labels", () => {
    expect(formatShoppingQuantity(item)).toBe("2 kg");
    expect(formatShoppingQuantity({ ...item, quantity: null, unit: null })).toBe("As needed");
    expect(getShoppingSourceLabel("manual")).toBe("Manual");
    expect(getShoppingSourceLabel("meal_plan")).toBe("From plan");
    expect(getShoppingSourceLabel("ai")).toBe("AI");
  });

  it("groups checked items before remaining items", () => {
    const checked = { ...item, id: 2, name: "milk", is_checked: true };
    const grouped = groupShoppingItems([item, checked]);
    expect(grouped).toEqual([
      { key: "checked", title: "Checked", data: [checked] },
      { key: "remaining", title: "Remaining", data: [item] },
    ]);
  });
});
