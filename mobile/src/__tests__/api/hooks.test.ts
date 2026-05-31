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

import { useDescribeReceipt, useParseShoppingDescription } from "@/api/hooks";

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
});
