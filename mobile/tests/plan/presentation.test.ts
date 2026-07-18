import {
  buildPlanSlots,
  formatPlanProgress,
  getCurrentWeekRangeLabel,
  getPlanRingModel,
  getPlanSubtitle,
} from "@/plan/presentation";
import type { MealPlanEntry } from "@/types";

const RING_CIRCUMFERENCE = 2 * Math.PI * 24;

const entry: MealPlanEntry = {
  id: 1,
  recipe_id: 7,
  planned_date: "2026-05-12",
  cooked_at: null,
  servings: 2,
  recipe_title: "Tomato Pasta",
};

describe("plan presentation", () => {
  it("formats plan progress and subtitle", () => {
    expect(formatPlanProgress(2, 5)).toEqual({ label: "2 of 5 dinners", percent: 40 });
    expect(getPlanSubtitle([entry], 5)).toBe("1 of 5 dinners");
  });

  it("builds real entries plus empty dinner slots", () => {
    const slots = buildPlanSlots([entry], 3);
    expect(slots).toEqual([
      { key: "entry-1", slotNumber: 1, entry },
      { key: "empty-1", slotNumber: 2, entry: null },
      { key: "empty-2", slotNumber: 3, entry: null },
    ]);
  });

  it("does not hide overflow entries beyond target", () => {
    const slots = buildPlanSlots([entry, { ...entry, id: 2, recipe_title: "Soup" }], 1);
    expect(slots.map((slot) => slot.key)).toEqual(["entry-1", "entry-2"]);
  });

  it("formats the current week range from a supplied date", () => {
    expect(getCurrentWeekRangeLabel(new Date("2026-05-12T12:00:00Z"))).toBe("11–17 May");
  });
});

describe("getPlanRingModel", () => {
  it("fills the ring proportionally for a normal case", () => {
    const ring = getPlanRingModel(2, 5);
    expect(ring.dashArray).toBe(`${0.4 * RING_CIRCUMFERENCE} ${RING_CIRCUMFERENCE}`);
    expect(ring.ratioLabel).toBe("2/5");
  });

  it("leaves the ring empty when the target is zero", () => {
    const ring = getPlanRingModel(3, 0);
    expect(ring.dashArray).toBe(`0 ${RING_CIRCUMFERENCE}`);
    expect(ring.ratioLabel).toBe("3/0");
  });

  it("clamps to a full ring when planned exceeds target", () => {
    const ring = getPlanRingModel(7, 5);
    expect(ring.dashArray).toBe(`${RING_CIRCUMFERENCE} ${RING_CIRCUMFERENCE}`);
    expect(ring.ratioLabel).toBe("7/5");
  });
});
