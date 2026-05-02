import { theme } from "@/theme";

describe("theme", () => {
  it("exports primary colour as teal", () => {
    expect(theme.colors.primary).toBe("#2a9d8f");
  });

  it("exports warm app surfaces", () => {
    expect(theme.colors.background).toBe("#fdfaf6");
    expect(theme.colors.surface).toBe("#f0e8de");
    expect(theme.colors.card).toBe("#ffffff");
    expect(theme.colors.muted).toBe("#f3eee8");
  });

  it("exports category colors for pantry groups", () => {
    expect(theme.categoryColors.vegetables).toBe("#4CAF50");
    expect(theme.categoryColors.protein).toBe("#F44336");
    expect(theme.categoryColors.dairy).toBe("#2196F3");
    expect(theme.categoryColors.carbohydrates).toBe("#FF9800");
    expect(theme.categoryColors.other).toBe("#64748B");
  });

  it("exports expiry colors for urgency badges", () => {
    expect(theme.expiryColors.expired).toBe("#EF4444");
    expect(theme.expiryColors.soon).toBe("#E07B39");
    expect(theme.expiryColors.later).toBe("#F59E0B");
  });

  it("has all required spacing keys in order", () => {
    expect(Object.keys(theme.spacing)).toEqual(["xs", "sm", "md", "lg", "xl", "xxl"]);
  });

  it("exports card shadow with warm shadow colour", () => {
    expect(theme.shadow.card.shadowColor).toBe("#2c1a0e");
  });
});
