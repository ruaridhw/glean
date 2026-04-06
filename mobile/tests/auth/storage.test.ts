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
    it("stores all four tokens in SecureStore", async () => {
      mockSetItem.mockResolvedValue(undefined);
      await authStorage.setTokens({
        access: "acc",
        refresh: "ref",
        id: "id",
        email: "user@example.com",
      });
      expect(mockSetItem).toHaveBeenCalledTimes(4);
      expect(mockSetItem).toHaveBeenCalledWith("glean_access_token", "acc");
      expect(mockSetItem).toHaveBeenCalledWith("glean_refresh_token", "ref");
      expect(mockSetItem).toHaveBeenCalledWith("glean_id_token", "id");
      expect(mockSetItem).toHaveBeenCalledWith("glean_email", "user@example.com");
    });
  });

  describe("getAccessToken", () => {
    it("returns the stored access token", async () => {
      mockGetItem.mockResolvedValue("my-token");
      const result = await authStorage.getAccessToken();
      expect(result).toBe("my-token");
      expect(mockGetItem).toHaveBeenCalledWith("glean_access_token");
    });
  });

  describe("clearTokens", () => {
    it("deletes all four keys", async () => {
      mockDeleteItem.mockResolvedValue(undefined);
      await authStorage.clearTokens();
      expect(mockDeleteItem).toHaveBeenCalledTimes(4);
    });
  });

  describe("hasTokens", () => {
    it("returns true when access token exists", async () => {
      mockGetItem.mockResolvedValue("some-token");
      expect(await authStorage.hasTokens()).toBe(true);
    });

    it("returns false when access token is null", async () => {
      mockGetItem.mockResolvedValue(null);
      expect(await authStorage.hasTokens()).toBe(false);
    });

    it("returns false when access token is empty string", async () => {
      mockGetItem.mockResolvedValue("");
      expect(await authStorage.hasTokens()).toBe(false);
    });
  });
});
