// mobile/tests/auth/storage.test.ts
jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

import * as SecureStore from "expo-secure-store";
import { authStorage } from "@/auth/storage";

const mockGetItem = SecureStore.getItemAsync as jest.Mock;
const mockSetItem = SecureStore.setItemAsync as jest.Mock;
const mockDeleteItem = SecureStore.deleteItemAsync as jest.Mock;

describe("authStorage", () => {
  beforeEach(() => jest.clearAllMocks());

  describe("setTokens", () => {
    it("stores all five tokens in SecureStore", async () => {
      mockSetItem.mockResolvedValue(undefined);
      await authStorage.setTokens({
        access: "acc",
        refresh: "ref",
        id: "id",
        email: "user@example.com",
        userSub: "sub-uuid",
      });
      expect(mockSetItem).toHaveBeenCalledTimes(5);
      expect(mockSetItem).toHaveBeenCalledWith("glean_access_token", "acc");
      expect(mockSetItem).toHaveBeenCalledWith("glean_refresh_token", "ref");
      expect(mockSetItem).toHaveBeenCalledWith("glean_id_token", "id");
      expect(mockSetItem).toHaveBeenCalledWith("glean_email", "user@example.com");
      expect(mockSetItem).toHaveBeenCalledWith("glean_user_sub", "sub-uuid");
    });
  });

  describe("getAccessToken", () => {
    it("returns CI token when EXPO_PUBLIC_CI_ACCESS_TOKEN is set", async () => {
      process.env.EXPO_PUBLIC_CI_ACCESS_TOKEN = "ci-token";
      const result = await authStorage.getAccessToken();
      expect(result).toBe("ci-token");
      expect(mockGetItem).not.toHaveBeenCalled();
      delete process.env.EXPO_PUBLIC_CI_ACCESS_TOKEN;
    });

    it("returns the stored access token in production", async () => {
      mockGetItem.mockResolvedValue("my-token");
      const result = await authStorage.getAccessToken();
      expect(result).toBe("my-token");
      expect(mockGetItem).toHaveBeenCalledWith("glean_access_token");
    });
  });

  describe("clearTokens", () => {
    it("deletes all five keys", async () => {
      mockDeleteItem.mockResolvedValue(undefined);
      await authStorage.clearTokens();
      expect(mockDeleteItem).toHaveBeenCalledTimes(5);
    });
  });

  describe("pending auth request", () => {
    it("stores the PKCE verifier and state", async () => {
      mockSetItem.mockResolvedValue(undefined);

      await authStorage.setPendingAuthRequest({
        codeVerifier: "verifier-123",
        state: "state-abc",
      });

      expect(mockSetItem).toHaveBeenCalledWith("glean_pending_auth_code_verifier", "verifier-123");
      expect(mockSetItem).toHaveBeenCalledWith("glean_pending_auth_state", "state-abc");
    });

    it("returns the verifier when the callback state matches", async () => {
      mockGetItem.mockResolvedValueOnce("verifier-123").mockResolvedValueOnce("state-abc");

      await expect(authStorage.getPendingAuthCodeVerifier("state-abc")).resolves.toBe(
        "verifier-123",
      );
    });

    it("does not return the verifier when the callback state does not match", async () => {
      mockGetItem.mockResolvedValueOnce("verifier-123").mockResolvedValueOnce("state-abc");

      await expect(authStorage.getPendingAuthCodeVerifier("other-state")).resolves.toBeNull();
    });

    it("clears the pending verifier and state", async () => {
      mockDeleteItem.mockResolvedValue(undefined);

      await authStorage.clearPendingAuthRequest();

      expect(mockDeleteItem).toHaveBeenCalledWith("glean_pending_auth_code_verifier");
      expect(mockDeleteItem).toHaveBeenCalledWith("glean_pending_auth_state");
    });
  });

  describe("hasTokens", () => {
    it("returns true in __DEV__ mode regardless of stored tokens", async () => {
      mockGetItem.mockResolvedValue(null);
      expect(await authStorage.hasTokens()).toBe(true);
      expect(mockGetItem).not.toHaveBeenCalled();
    });

    it("returns true when CI tokens are set", async () => {
      process.env.EXPO_PUBLIC_CI_ACCESS_TOKEN = "ci-token";
      const result = await authStorage.hasTokens();
      expect(result).toBe(true);
      delete process.env.EXPO_PUBLIC_CI_ACCESS_TOKEN;
    });
  });

  describe("getUserSub", () => {
    it("returns dev-user-sub in __DEV__ mode", async () => {
      const result = await authStorage.getUserSub();
      expect(result).toBe("dev-user-sub");
      expect(mockGetItem).not.toHaveBeenCalled();
    });
  });
});
