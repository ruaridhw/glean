import { shouldRunSwipeAction } from "@/shop/use-swipe-action";

describe("useSwipeAction helpers", () => {
  it("runs the action for a decisive left swipe", () => {
    expect(shouldRunSwipeAction({ translationX: -64, translationY: 8 })).toBe(true);
  });

  it("ignores short or mostly vertical gestures", () => {
    expect(shouldRunSwipeAction({ translationX: -32, translationY: 4 })).toBe(false);
    expect(shouldRunSwipeAction({ translationX: -72, translationY: 96 })).toBe(false);
    expect(shouldRunSwipeAction({ translationX: 72, translationY: 4 })).toBe(false);
  });
});
