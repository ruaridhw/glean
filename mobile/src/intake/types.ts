// mobile/src/intake/types.ts
//
// Shared shape for the AI-intake review screens (pantry scan/describe →
// pantry/review, shop describe → shop/review). Both flows send an
// AI-extracted list of candidate items to a review screen as a nav param,
// let the user edit/remove rows, then persist the accepted ones.

export interface ReviewItem {
  /**
   * Stable per-item identity assigned once, when the nav-param payload is
   * parsed (see `deserializeReviewItems`). Used as list key; never persisted.
   */
  review_id: string;
  name: string;
  quantity: number;
  unit: string;
  confidence: number;
}
