// mobile/src/shop/intake.ts
//
// Commit side of the shopping AI-intake review screen (shop/review.tsx):
// takes the edited review rows and persists the accepted ones to the local
// shopping list.

import { addAiShoppingItems } from "@/db/shopping";
import type { ReviewItem } from "@/intake/types";
import { normalizeSubmittedText, toRequiredSubmittedText } from "@/normalization/text-input";

export type ShopReviewItem = ReviewItem & {
  api_ingredient_id: string | null;
  category: string | null;
};

/**
 * Persist the accepted rows (name not cleared) from the shopping review
 * screen to the local shopping list. Returns how many were saved, for the
 * screen's success toast.
 */
export async function commitShoppingIntake(items: readonly ShopReviewItem[]): Promise<number> {
  const accepted = items
    .filter((item) => toRequiredSubmittedText(item.name))
    .map((item) => ({
      name: toRequiredSubmittedText(item.name) as string,
      quantity: item.quantity,
      unit: normalizeSubmittedText(item.unit) || "units",
      api_ingredient_id: item.api_ingredient_id,
      category: item.category,
    }));
  await addAiShoppingItems(accepted);
  return accepted.length;
}
