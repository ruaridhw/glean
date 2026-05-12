import {
  buildPlanSlots,
  formatPlanProgress,
  getCurrentWeekRangeLabel,
  getPlanSubtitle,
} from "@/plan/presentation";
import type { MealPlanEntry } from "@/types";

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
    expect(getCurrentWeekRangeLabel(new Date("2026-05-12T12:00:00Z"))).toBe("11-17 May");
  });
});
