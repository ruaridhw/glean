import * as Haptics from "expo-haptics";

export type HapticImpact = "light" | "medium";
export type HapticNotification = "success" | "warning";

const impactMap: Record<HapticImpact, Haptics.ImpactFeedbackStyle> = {
  light: Haptics.ImpactFeedbackStyle.Light,
  medium: Haptics.ImpactFeedbackStyle.Medium,
};

const notificationMap: Record<HapticNotification, Haptics.NotificationFeedbackType> = {
  success: Haptics.NotificationFeedbackType.Success,
  warning: Haptics.NotificationFeedbackType.Warning,
};

export async function hapticImpact(style: HapticImpact = "light"): Promise<void> {
  try {
    await Haptics.impactAsync(impactMap[style]);
  } catch {
    // Haptics are polish only. Unsupported platforms must not break app behavior.
  }
}

export async function hapticNotify(type: HapticNotification): Promise<void> {
  try {
    await Haptics.notificationAsync(notificationMap[type]);
  } catch {
    // Haptics are polish only. Unsupported platforms must not break app behavior.
  }
}
