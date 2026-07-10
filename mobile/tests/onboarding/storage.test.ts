jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
}));

import * as SecureStore from "expo-secure-store";
import { completeOnboarding, hasCompletedOnboarding } from "@/onboarding/storage";

const mockGetItem = SecureStore.getItemAsync as jest.Mock;
const mockSetItem = SecureStore.setItemAsync as jest.Mock;

describe("onboarding storage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns true only when the completion flag is stored as true", async () => {
    mockGetItem
      .mockResolvedValueOnce("true")
      .mockResolvedValueOnce("false")
      .mockResolvedValueOnce(null);

    await expect(hasCompletedOnboarding()).resolves.toBe(true);
    await expect(hasCompletedOnboarding()).resolves.toBe(false);
    await expect(hasCompletedOnboarding()).resolves.toBe(false);
    expect(mockGetItem).toHaveBeenCalledWith("glean_onboarding_complete");
  });

  it("fails open to first-run onboarding when the flag cannot be read", async () => {
    const error = new Error("secure store unavailable");
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    mockGetItem.mockRejectedValueOnce(error);

    await expect(hasCompletedOnboarding()).resolves.toBe(false);
    expect(warnSpy).toHaveBeenCalledWith("[onboarding] completion flag read failed:", error);
    warnSpy.mockRestore();
  });

  it("stores the completion flag", async () => {
    mockSetItem.mockResolvedValueOnce(undefined);

    await completeOnboarding();

    expect(mockSetItem).toHaveBeenCalledWith("glean_onboarding_complete", "true");
  });
});
