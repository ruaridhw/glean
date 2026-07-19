// mobile/src/intake/presentation.ts

import type { ReviewItem } from "./types";

const LOW_CONFIDENCE_THRESHOLD = 0.7;

/** Whether an AI-extracted review row is uncertain enough to flag for a manual check. */
export function isLowConfidence(item: Pick<ReviewItem, "confidence">): boolean {
  return item.confidence < LOW_CONFIDENCE_THRESHOLD;
}
