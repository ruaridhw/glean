import { deserializeReviewItems, serializeReviewItems } from "@/intake/serialization";
import type { ReviewItem } from "@/intake/types";

describe("intake serialization", () => {
  it("serializes items as plain JSON", () => {
    const payload = serializeReviewItems([
      { name: "milk", quantity: 1, unit: "bottle", confidence: 0.9 },
    ]);
    expect(payload).toBe(
      JSON.stringify([{ name: "milk", quantity: 1, unit: "bottle", confidence: 0.9 }]),
    );
  });

  it("assigns a stable review_id to each row when deserializing", () => {
    const raw = JSON.stringify([
      { name: "milk", quantity: 1, unit: "bottle", confidence: 0.9 },
      { name: "eggs", quantity: 6, unit: "unit", confidence: 0.4 },
    ]);

    const items = deserializeReviewItems<ReviewItem>(raw);

    expect(items).toEqual([
      { name: "milk", quantity: 1, unit: "bottle", confidence: 0.9, review_id: "0" },
      { name: "eggs", quantity: 6, unit: "unit", confidence: 0.4, review_id: "1" },
    ]);
  });

  it("gives duplicate-looking rows distinct identity", () => {
    const raw = JSON.stringify([
      { name: "milk", quantity: 1, unit: "bottle", confidence: 0.9 },
      { name: "milk", quantity: 1, unit: "bottle", confidence: 0.9 },
    ]);

    const items = deserializeReviewItems<ReviewItem>(raw);

    expect(new Set(items.map((item) => item.review_id)).size).toBe(2);
  });

  it("returns an empty array for a missing payload", () => {
    expect(deserializeReviewItems<ReviewItem>(undefined)).toEqual([]);
  });
});
