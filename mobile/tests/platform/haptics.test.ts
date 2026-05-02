jest.mock("expo-haptics", () => ({
  ImpactFeedbackStyle: { Light: "Light", Medium: "Medium" },
  NotificationFeedbackType: { Success: "Success", Warning: "Warning" },
  impactAsync: jest.fn().mockResolvedValue(undefined),
  notificationAsync: jest.fn().mockResolvedValue(undefined),
}));

import * as ExpoHaptics from "expo-haptics";
import { hapticImpact, hapticNotify } from "@/platform/haptics";

describe("haptics wrapper", () => {
  it("sends light impact feedback", async () => {
    await hapticImpact("light");
    expect(ExpoHaptics.impactAsync).toHaveBeenCalledWith(ExpoHaptics.ImpactFeedbackStyle.Light);
  });

  it("sends success notification feedback", async () => {
    await hapticNotify("success");
    expect(ExpoHaptics.notificationAsync).toHaveBeenCalledWith(
      ExpoHaptics.NotificationFeedbackType.Success,
    );
  });

  it("swallows haptic failures", async () => {
    (ExpoHaptics.impactAsync as jest.Mock).mockRejectedValueOnce(new Error("unavailable"));
    await expect(hapticImpact("medium")).resolves.toBeUndefined();
  });
});
