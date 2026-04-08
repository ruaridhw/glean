/** @jest-environment node */
// mobile/src/__tests__/normalization/units.test.ts
import { normalizeUnit } from "@/normalization/units";

describe("normalizeUnit", () => {
  it("returns identity when unit matches canonical_unit", () => {
    const result = normalizeUnit({
      quantity: 500,
      unit: "g",
      canonicalUnit: "g",
      canonicalName: "chicken breast",
    });
    expect(result).toEqual({ quantity: 500, unit: "g", source: "identity" });
  });

  it("returns identity when canonical_unit is null", () => {
    const result = normalizeUnit({
      quantity: 2,
      unit: "units",
      canonicalUnit: null,
      canonicalName: "egg",
    });
    expect(result).toEqual({ quantity: 2, unit: "units", source: "identity" });
  });

  it("converts kg → g", () => {
    const result = normalizeUnit({
      quantity: 0.5,
      unit: "kg",
      canonicalUnit: "g",
      canonicalName: "beef mince",
    });
    expect(result?.quantity).toBeCloseTo(500, 1);
    expect(result?.unit).toBe("g");
    expect(result?.source).toBe("lookup");
  });

  it("converts L → ml", () => {
    const result = normalizeUnit({
      quantity: 1.5,
      unit: "l",
      canonicalUnit: "ml",
      canonicalName: "whole milk",
    });
    expect(result?.quantity).toBeCloseTo(1500, 1);
    expect(result?.unit).toBe("ml");
    expect(result?.source).toBe("lookup");
  });

  it("converts cup of flour → g via density", () => {
    const result = normalizeUnit({
      quantity: 1,
      unit: "cup",
      canonicalUnit: "g",
      canonicalName: "plain flour",
    });
    // 1 cup = 236.588ml × 0.593 g/ml ≈ 140.3g
    expect(result?.quantity).toBeCloseTo(140.3, 0);
    expect(result?.unit).toBe("g");
    expect(result?.source).toBe("density");
  });

  it("returns null for unknown ambiguous conversion", () => {
    const result = normalizeUnit({
      quantity: 1,
      unit: "head",
      canonicalUnit: "units",
      canonicalName: "garlic",
    });
    expect(result).toBeNull();
  });
});
