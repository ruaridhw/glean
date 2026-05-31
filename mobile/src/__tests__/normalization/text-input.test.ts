import { normalizeSubmittedText, toRequiredSubmittedText } from "@/normalization/text-input";

describe("text input normalization", () => {
  it("trims outer whitespace while preserving intentional multiline spacing", () => {
    expect(normalizeSubmittedText(" \n  milk\n  sourdough bread  \n\t")).toBe(
      "milk\n  sourdough bread",
    );
  });

  it("returns null for values that are empty after trimming", () => {
    expect(toRequiredSubmittedText(" \n\t  ")).toBeNull();
  });
});
