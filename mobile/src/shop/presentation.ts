import type { ShoppingListItem } from "@/types";

export interface ShoppingSection {
  key: "toBuy" | "inCart";
  title: string;
  data: ShoppingListItem[];
}

type ShoppingSourceTone = "primary" | "neutral";

/** Bold row label — "name · 200 g", or just the name when there's no quantity. */
export function formatShoppingItemLabel(
  item: Pick<ShoppingListItem, "name" | "quantity" | "unit">,
): string {
  if (item.quantity == null) return item.name;
  const quantity = [item.quantity, item.unit].filter(Boolean).join(" ");
  return quantity ? `${item.name} · ${quantity}` : item.name;
}

export function getShoppingSourceLabel(source: ShoppingListItem["source"]): string {
  if (source === "meal_plan") return "Plan";
  if (source === "ai") return "AI";
  return "Manual";
}

export function getShoppingSourceTone(source: ShoppingListItem["source"]): ShoppingSourceTone {
  return source === "meal_plan" ? "primary" : "neutral";
}

export function groupShoppingItems(items: ShoppingListItem[]): ShoppingSection[] {
  const toBuy = items.filter((item) => !item.is_checked);
  const inCart = items.filter((item) => item.is_checked);
  return [
    { key: "toBuy" as const, title: "To buy", data: toBuy },
    { key: "inCart" as const, title: "In your cart", data: inCart },
  ].filter((section) => section.data.length > 0);
}
