import { isLowConfidence } from "@/intake/presentation";

describe("intake presentation", () => {
  it("flags rows below the confidence threshold", () => {
    expect(isLowConfidence({ confidence: 0.69 })).toBe(true);
    expect(isLowConfidence({ confidence: 0 })).toBe(true);
  });

  it("does not flag rows at or above the threshold", () => {
    expect(isLowConfidence({ confidence: 0.7 })).toBe(false);
    expect(isLowConfidence({ confidence: 1 })).toBe(false);
  });
});
