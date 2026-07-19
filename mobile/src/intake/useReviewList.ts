// mobile/src/intake/useReviewList.ts

import { useState } from "react";
import { toRequiredSubmittedText } from "@/normalization/text-input";
import type { ReviewItem } from "./types";

interface UseReviewListResult<T extends ReviewItem> {
  items: T[];
  updateItem: (index: number, patch: Partial<T>) => void;
  removeItem: (index: number) => void;
  /** Rows whose name hasn't been cleared out — what confirm() actually persists. */
  acceptedItems: T[];
  acceptedCount: number;
}

/**
 * Shared editable-list state for an AI-intake review screen: update/remove a
 * row by index, plus the "accepted" subset used for both the confirm
 * button's count and what a screen's commit function should persist.
 */
export function useReviewList<T extends ReviewItem>(
  initialItems: T[] | (() => T[]),
): UseReviewListResult<T> {
  const [items, setItems] = useState<T[]>(initialItems);

  function updateItem(index: number, patch: Partial<T>) {
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  function removeItem(index: number) {
    setItems((prev) => prev.filter((_, i) => i !== index));
  }

  const acceptedItems = items.filter((item) => Boolean(toRequiredSubmittedText(item.name)));

  return { items, updateItem, removeItem, acceptedItems, acceptedCount: acceptedItems.length };
}
