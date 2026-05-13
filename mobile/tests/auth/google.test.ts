jest.mock("expo-auth-session", () => ({
  exchangeCodeAsync: jest.fn(),
  revokeAsync: jest.fn(),
}));

jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

jest.mock("@/auth/storage", () => ({
  authStorage: {
    setTokens: jest.fn(),
    getRefreshToken: jest.fn(),
    clearTokens: jest.fn(),
  },
}));

import { exchangeCodeAsync } from "expo-auth-session";
import { handleAuthCode, refreshTokens, signOut } from "@/auth/google";
import { authStorage } from "@/auth/storage";

const mockExchangeCode = exchangeCodeAsync as jest.Mock;

describe("google auth", () => {
  beforeEach(() => jest.clearAllMocks());

  describe("handleAuthCode", () => {
    it("exchanges code for tokens and stores them", async () => {
      mockExchangeCode.mockResolvedValue({
        accessToken: "access-123",
        refreshToken: "refresh-123",
        idToken:
          "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyLXN1Yi0xMjMiLCJlbWFpbCI6InRlc3RAZ21haWwuY29tIn0.sig",
      });

      await handleAuthCode("auth-code-xyz", "code-verifier-abc");

      expect(mockExchangeCode).toHaveBeenCalledTimes(1);
      expect(authStorage.setTokens as jest.Mock).toHaveBeenCalledWith({
        access: "access-123",
        refresh: "refresh-123",
        id: "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyLXN1Yi0xMjMiLCJlbWFpbCI6InRlc3RAZ21haWwuY29tIn0.sig",
        email: "test@gmail.com",
        userSub: "user-sub-123",
      });
    });
  });

  describe("refreshTokens", () => {
    it("returns false when no refresh token is stored", async () => {
      (authStorage.getRefreshToken as jest.Mock).mockResolvedValue(null);
      const result = await refreshTokens();
      expect(result).toBe(false);
    });
  });

  describe("signOut", () => {
    it("clears tokens from storage", async () => {
      await signOut();
      expect(authStorage.clearTokens).toHaveBeenCalledTimes(1);
    });
  });
});
