import { commitShoppingIntake } from "@/shop/intake";

const mockAddAiShoppingItems = jest.fn();

jest.mock("@/db/shopping", () => ({
  addAiShoppingItems: (...args: unknown[]) => mockAddAiShoppingItems(...args),
}));

describe("commitShoppingIntake", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAddAiShoppingItems.mockResolvedValue(undefined);
  });

  it("persists accepted rows, trimming names and normalizing units", () => {
    return commitShoppingIntake([
      {
        review_id: "0",
        name: "  taco shells ",
        quantity: 1,
        unit: "",
        confidence: 0.82,
        api_ingredient_id: "taco-shells",
        category: "bakery",
      },
      {
        review_id: "1",
        name: "whole milk",
        quantity: 1,
        unit: "bottle",
        confidence: 0.91,
        api_ingredient_id: null,
        category: "dairy",
      },
    ]).then((savedCount) => {
      expect(mockAddAiShoppingItems).toHaveBeenCalledWith([
        {
          name: "taco shells",
          quantity: 1,
          unit: "units",
          api_ingredient_id: "taco-shells",
          category: "bakery",
        },
        {
          name: "whole milk",
          quantity: 1,
          unit: "bottle",
          api_ingredient_id: null,
          category: "dairy",
        },
      ]);
      expect(savedCount).toBe(2);
    });
  });

  it("drops rows whose name has been cleared and doesn't count them", async () => {
    const savedCount = await commitShoppingIntake([
      {
        review_id: "0",
        name: "   ",
        quantity: 1,
        unit: "bottle",
        confidence: 0.9,
        api_ingredient_id: null,
        category: null,
      },
      {
        review_id: "1",
        name: "bananas",
        quantity: 3,
        unit: "unit",
        confidence: 0.9,
        api_ingredient_id: null,
        category: "produce",
      },
    ]);

    expect(mockAddAiShoppingItems).toHaveBeenCalledWith([
      {
        name: "bananas",
        quantity: 3,
        unit: "unit",
        api_ingredient_id: null,
        category: "produce",
      },
    ]);
    expect(savedCount).toBe(1);
  });

  it("does not touch the DB when nothing is accepted", async () => {
    const savedCount = await commitShoppingIntake([]);

    expect(mockAddAiShoppingItems).toHaveBeenCalledWith([]);
    expect(savedCount).toBe(0);
  });
});
