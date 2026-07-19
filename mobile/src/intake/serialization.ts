// mobile/src/intake/serialization.ts
//
// The only place that (de)serializes the `items` nav param shared by the
// AI-intake review screens. Callers hand over freshly-parsed API items (no
// identity yet); `deserializeReviewItems` assigns each a stable `review_id`
// as it types the payload, so identity is derived exactly once instead of
// being re-hydrated ad hoc per screen.

import type { ReviewItem } from "./types";

/** Encode AI-extracted items into the nav-param payload for a review screen. */
export function serializeReviewItems<T>(items: T[]): string {
  return JSON.stringify(items);
}

/** Decode a review screen's `items` nav param, assigning each row a `review_id`. */
export function deserializeReviewItems<T extends ReviewItem>(raw: string | undefined): T[] {
  if (!raw) return [];
  const items = JSON.parse(raw) as Omit<T, "review_id">[];
  return items.map((item, index) => ({ ...item, review_id: String(index) })) as T[];
}
