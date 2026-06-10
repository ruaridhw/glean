// mobile/src/meal-plan/compress.ts

export interface PantryItemForCompression {
  ingredient_id: number;
  canonical_name: string;
  quantity: number;
  unit: string;
  expiry_date: string | null;
  last_used_at: string | null;
  is_staple: boolean;
  food_group: string;
}

interface CompressedPantryItem {
  id: number;
  name: string;
  quantity: number;
  unit: string;
  food_group: string;
  urgency_score: number;
}

const MS_PER_DAY = 1000 * 60 * 60 * 24;

// Scores a pantry item's urgency (higher = more urgent to use).
// Factors: expiry proximity, time since last use, quantity level.
export function scorePantryItem(item: PantryItemForCompression, now: Date = new Date()): number {
  let score = 0;

  if (item.expiry_date) {
    const daysUntilExpiry = (new Date(item.expiry_date).getTime() - now.getTime()) / MS_PER_DAY;
    if (daysUntilExpiry <= 1) score += 100;
    else if (daysUntilExpiry <= 3) score += 50;
    else if (daysUntilExpiry <= 7) score += 20;
  }

  if (item.last_used_at) {
    const daysSinceUsed = (now.getTime() - new Date(item.last_used_at).getTime()) / MS_PER_DAY;
    score += Math.min(30, daysSinceUsed); // Cap at 30 points
  } else {
    score += 15; // Never used — moderate urgency
  }

  if (item.quantity > 0 && item.quantity < 100) score += 10;

  return score;
}

// Compresses full pantry to top-N items by urgency score.
// Excludes staples (assumed always available).
export function compressPantry(
  items: PantryItemForCompression[],
  topN: number = 15,
  now: Date = new Date(),
): CompressedPantryItem[] {
  return items
    .filter((item) => !item.is_staple && item.quantity > 0)
    .map((item) => ({ ...item, urgency_score: scorePantryItem(item, now) }))
    .sort((a, b) => b.urgency_score - a.urgency_score)
    .slice(0, topN)
    .map((item) => ({
      id: item.ingredient_id,
      name: item.canonical_name,
      quantity: item.quantity,
      unit: item.unit,
      food_group: item.food_group,
      urgency_score: item.urgency_score,
    }));
}
