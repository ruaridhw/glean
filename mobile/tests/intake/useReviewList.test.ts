import { act, renderHook } from "@testing-library/react-native";
import type { ReviewItem } from "@/intake/types";
import { useReviewList } from "@/intake/useReviewList";

function makeItems(): ReviewItem[] {
  return [
    { review_id: "0", name: "milk", quantity: 1, unit: "bottle", confidence: 0.9 },
    { review_id: "1", name: "eggs", quantity: 6, unit: "unit", confidence: 0.4 },
    { review_id: "2", name: "bread", quantity: 1, unit: "loaf", confidence: 0.95 },
  ];
}

describe("useReviewList", () => {
  it("counts every row as accepted initially", () => {
    const { result } = renderHook(() => useReviewList<ReviewItem>(makeItems()));

    expect(result.current.items).toHaveLength(3);
    expect(result.current.acceptedCount).toBe(3);
    expect(result.current.acceptedItems).toEqual(makeItems());
  });

  it("patches a single row by index without touching the others", () => {
    const { result } = renderHook(() => useReviewList<ReviewItem>(makeItems()));

    act(() => {
      result.current.updateItem(1, { name: "large eggs", quantity: 12 });
    });

    expect(result.current.items[1]).toMatchObject({ name: "large eggs", quantity: 12 });
    expect(result.current.items[0]?.name).toBe("milk");
    expect(result.current.items[2]?.name).toBe("bread");
  });

  it("removes a row by index", () => {
    const { result } = renderHook(() => useReviewList<ReviewItem>(makeItems()));

    act(() => {
      result.current.removeItem(0);
    });

    expect(result.current.items.map((item) => item.review_id)).toEqual(["1", "2"]);
    expect(result.current.acceptedCount).toBe(2);
  });

  it("excludes rows whose name has been cleared from the accepted subset", () => {
    const { result } = renderHook(() => useReviewList<ReviewItem>(makeItems()));

    act(() => {
      result.current.updateItem(1, { name: "   " });
    });

    expect(result.current.items).toHaveLength(3);
    expect(result.current.acceptedCount).toBe(2);
    expect(result.current.acceptedItems.map((item) => item.review_id)).toEqual(["0", "2"]);
  });

  it("accepts a lazy initializer, matching useState semantics", () => {
    const initializer = jest.fn(makeItems);
    const { result } = renderHook(() => useReviewList<ReviewItem>(initializer));

    expect(initializer).toHaveBeenCalledTimes(1);
    expect(result.current.items).toHaveLength(3);
  });
});
