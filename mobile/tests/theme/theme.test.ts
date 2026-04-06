import { theme } from "@/theme";

describe("theme", () => {
  it("exports primary colour as teal", () => {
    expect(theme.colors.primary).toBe("#2a9d8f");
  });

  it("exports background as warm cream", () => {
    expect(theme.colors.background).toBe("#fdfaf6");
  });

  it("exports warning as terracotta", () => {
    expect(theme.colors.warning).toBe("#e07c3c");
  });

  it("has all required spacing keys in order", () => {
    expect(Object.keys(theme.spacing)).toEqual(["xs", "sm", "md", "lg", "xl", "xxl"]);
  });

  it("exports card shadow with warm shadow colour", () => {
    expect(theme.shadow.card.shadowColor).toBe("#2c1a0e");
  });
});
