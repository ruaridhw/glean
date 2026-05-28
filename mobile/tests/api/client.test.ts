// mobile/tests/api/client.test.ts
jest.mock("@/auth/storage", () => ({
  authStorage: {
    getAccessToken: jest.fn(),
  },
}));

jest.mock("@/auth/google", () => ({
  refreshTokens: jest.fn(),
}));

import { ApiError, apiClient } from "@/api/client";
import { refreshTokens } from "@/auth/google";
import { authStorage } from "@/auth/storage";

const mockGetAccessToken = authStorage.getAccessToken as jest.Mock;
const mockRefreshTokens = refreshTokens as jest.Mock;

describe("apiClient", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn();
    mockGetAccessToken.mockResolvedValue("valid-token");
  });

  describe("get", () => {
    it("sends Bearer token in Authorization header", async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        status: 200,
        json: jest.fn().mockResolvedValue({ data: "ok" }),
      });

      await apiClient.get("/health");

      const [, init] = (global.fetch as jest.Mock).mock.calls[0]!;
      expect((init.headers as Record<string, string>).Authorization).toBe("Bearer valid-token");
    });

    it("throws ApiError on non-2xx response", async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        status: 500,
        json: jest.fn().mockResolvedValue({ detail: "Server error" }),
      });

      await expect(apiClient.get("/health")).rejects.toBeInstanceOf(ApiError);
    });
  });

  describe("401 refresh and retry", () => {
    it("refreshes tokens and retries on 401", async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: jest.fn().mockResolvedValue({ detail: "Unauthorized" }),
        })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: jest.fn().mockResolvedValue({ data: "ok" }),
        });

      mockRefreshTokens.mockResolvedValue(true);
      mockGetAccessToken.mockResolvedValueOnce("old-token").mockResolvedValueOnce("new-token");

      const result = await apiClient.get("/protected");
      expect(mockRefreshTokens).toHaveBeenCalledTimes(1);
      expect(global.fetch).toHaveBeenCalledTimes(2);
      expect(result).toEqual({ data: "ok" });
    });

    it("throws ApiError with 401 when refresh fails", async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        status: 401,
        json: jest.fn().mockResolvedValue({ detail: "Unauthorized" }),
      });

      mockRefreshTokens.mockResolvedValue(false);

      const error = await apiClient.get("/protected").catch((e: unknown) => e);
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(401);
    });
  });
});
