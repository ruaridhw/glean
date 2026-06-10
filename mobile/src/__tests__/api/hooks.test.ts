const mockPost = jest.fn();

jest.mock("@tanstack/react-query", () => ({
  useMutation: jest.fn((config: unknown) => config),
  useQuery: jest.fn((config: unknown) => config),
}));

jest.mock("@/api/client", () => ({
  apiClient: {
    get: jest.fn(),
    post: (...args: unknown[]) => mockPost(...args),
    postForm: jest.fn(),
  },
}));

import { useDescribeReceipt, useGenerateMealPlan, useParseShoppingDescription } from "@/api/hooks";

describe("API text submission hooks", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPost.mockResolvedValue({ items: [], clarifying_questions: [] });
  });

  it("trims receipt descriptions before submitting them to the API", async () => {
    const mutation = useDescribeReceipt() as unknown as {
      mutationFn: (text: string) => Promise<unknown>;
    };

    await mutation.mutationFn(" \n  milk\n  sourdough bread  \t");

    expect(mockPost).toHaveBeenCalledWith("/receipts/describe", {
      text: "milk\n  sourdough bread",
    });
  });

  it("rejects shopping descriptions that are empty after trimming", async () => {
    const mutation = useParseShoppingDescription() as unknown as {
      mutationFn: (body: { text: string }) => Promise<unknown>;
    };

    await expect(mutation.mutationFn({ text: " \n\t  " })).rejects.toThrow(
      "Text input cannot be empty",
    );
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("posts meal-plan generation requests to the meal-plan API", async () => {
    const mutation = useGenerateMealPlan() as unknown as {
      mutationFn: (body: {
        pantry: unknown[];
        recipe_history: unknown[];
        food_group_coverage: Record<string, never>;
        purchase_tolerance: number;
        meals_per_week: number;
        dietary_flags: string[];
        max_active_time_mins: number | null;
      }) => Promise<unknown>;
    };

    const body = {
      pantry: [],
      recipe_history: [],
      food_group_coverage: {},
      purchase_tolerance: 0.5,
      meals_per_week: 3,
      dietary_flags: [],
      max_active_time_mins: null,
    };
    await mutation.mutationFn(body);

    expect(mockPost).toHaveBeenCalledWith("/meal-plan", body);
  });
});
