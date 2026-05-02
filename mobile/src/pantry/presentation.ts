import { theme } from "@/theme";
import type { PantryItem } from "@/types";

type CategoryKey = keyof typeof theme.categoryColors;

export interface PantryCategoryMeta {
  key: CategoryKey;
  label: string;
  color: string;
  icon: string;
}

export interface PantrySection {
  key: string;
  title: string;
  meta: PantryCategoryMeta;
  items: PantryItem[];
}

export interface ExpiryBadgeModel {
  label: string;
  tone: "expired" | "soon" | "later";
}

const categoryMeta: Record<CategoryKey, Omit<PantryCategoryMeta, "key" | "color">> = {
  vegetables: { label: "Veg & Fruit", icon: "leaf-outline" },
  fruit: { label: "Veg & Fruit", icon: "leaf-outline" },
  protein: { label: "Meat & Fish", icon: "fish-outline" },
  dairy: { label: "Dairy", icon: "water-outline" },
  carbohydrates: { label: "Cupboard", icon: "cube-outline" },
  fats: { label: "Cupboard", icon: "cube-outline" },
  condiments: { label: "Cupboard", icon: "cube-outline" },
  frozen: { label: "Frozen", icon: "snow-outline" },
  other: { label: "Other", icon: "cube-outline" },
};

function isCategoryKey(value: string | null | undefined): value is CategoryKey {
  return Boolean(value && value in theme.categoryColors);
}

export function getPantryCategoryMeta(foodGroup: string | null | undefined): PantryCategoryMeta {
  const key: CategoryKey = isCategoryKey(foodGroup) ? foodGroup : "other";
  return {
    key,
    label: categoryMeta[key].label,
    color: theme.categoryColors[key],
    icon: categoryMeta[key].icon,
  };
}

export function formatPantryQuantity(item: Pick<PantryItem, "quantity" | "unit">): string {
  return `${Number.isInteger(item.quantity) ? item.quantity.toFixed(0) : item.quantity} ${item.unit}`;
}

export function groupPantryItems(items: PantryItem[]): PantrySection[] {
  const sections = new Map<string, PantrySection>();

  for (const item of items) {
    const meta = getPantryCategoryMeta(item.food_group);
    const existing = sections.get(meta.label);
    if (existing) {
      existing.items.push(item);
    } else {
      sections.set(meta.label, {
        key: meta.label,
        title: meta.label,
        meta,
        items: [item],
      });
    }
  }

  return Array.from(sections.values());
}

export function getExpiryBadge(
  expiryDate: string | null | undefined,
  now: Date = new Date(),
): ExpiryBadgeModel | null {
  if (!expiryDate) return null;

  const today = new Date(now);
  today.setHours(0, 0, 0, 0);
  const expiry = new Date(`${expiryDate}T00:00:00`);
  const days = Math.round((expiry.getTime() - today.getTime()) / 86_400_000);

  if (days < 0) return { label: "Expired", tone: "expired" };
  if (days === 0) return { label: "Today", tone: "expired" };
  if (days <= 2) return { label: `${days}d left`, tone: "soon" };
  return { label: `${days}d left`, tone: "later" };
}
