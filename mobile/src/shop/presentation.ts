import type { ShoppingListItem } from "@/types";

export interface ShoppingSection {
  key: "remaining" | "checked";
  title: string;
  items: ShoppingListItem[];
}

export function formatShoppingQuantity(item: Pick<ShoppingListItem, "quantity" | "unit">): string {
  if (item.quantity == null) return "As needed";
  return [item.quantity, item.unit].filter(Boolean).join(" ");
}

export function getShoppingSourceLabel(source: ShoppingListItem["source"]): string {
  if (source === "meal_plan") return "From plan";
  if (source === "ai") return "AI";
  return "Manual";
}

export function groupShoppingItems(items: ShoppingListItem[]): ShoppingSection[] {
  const remaining = items.filter((item) => !item.is_checked);
  const checked = items.filter((item) => item.is_checked);
  return [
    { key: "remaining" as const, title: "Remaining", items: remaining },
    { key: "checked" as const, title: "Checked", items: checked },
  ].filter((section) => section.items.length > 0);
}
