import * as SecureStore from "expo-secure-store";

const ONBOARDING_COMPLETE_KEY = "glean_onboarding_complete";

export async function hasCompletedOnboarding(): Promise<boolean> {
  try {
    return (await SecureStore.getItemAsync(ONBOARDING_COMPLETE_KEY)) === "true";
  } catch (error) {
    console.warn("[onboarding] completion flag read failed:", error);
    return false;
  }
}

export async function completeOnboarding(): Promise<void> {
  await SecureStore.setItemAsync(ONBOARDING_COMPLETE_KEY, "true");
}
