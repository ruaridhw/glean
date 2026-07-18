import {
  buildIntegerOptions,
  DIETARY_OPTIONS,
  getToleranceLabel,
  SETTINGS_OPTION_RANGES,
  validateBoundedInteger,
} from "@/settings/presentation";

describe("settings presentation", () => {
  it("derives numeric settings options from the original model ranges", () => {
    expect(buildIntegerOptions(SETTINGS_OPTION_RANGES.dinnersPerWeek)).toEqual([3, 4, 5, 6, 7]);
    expect(buildIntegerOptions(SETTINGS_OPTION_RANGES.defaultServings)).toEqual([1, 2, 3, 4, 5, 6]);
    expect(DIETARY_OPTIONS).toContain("Vegetarian");
  });

  it("formats purchase tolerance labels", () => {
    expect(getToleranceLabel(0.1)).toBe("Strict: pantry ingredients only");
    expect(getToleranceLabel(0.5)).toBe("Moderate: minor shopping OK");
    expect(getToleranceLabel(0.9)).toBe("Open: happy to buy new ingredients");
  });

  it("validates bounded integer input", () => {
    expect(validateBoundedInteger("", 1, 7, "Meals")).toBe("Meals is required");
    expect(validateBoundedInteger("0", 1, 7, "Meals")).toBe("Meals must be between 1 and 7");
    expect(validateBoundedInteger("5", 1, 7, "Meals")).toBeNull();
  });
});
