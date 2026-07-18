import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, View } from "react-native";
import { theme } from "@/theme";
import { AppText } from "./AppText";

interface ErrorStateProps {
  message?: string;
  onRetry: () => void;
  testID?: string;
}

export function ErrorState({
  message = "Something went wrong. Please try again.",
  onRetry,
  testID,
}: ErrorStateProps) {
  return (
    <View style={s.container} testID={testID}>
      <Ionicons name="alert-circle-outline" size={48} color={theme.colors.warning} style={s.icon} />
      <AppText style={s.message}>{message}</AppText>
      <Pressable
        style={({ pressed }) => [s.retryBtn, pressed && s.retryBtnPressed]}
        onPress={onRetry}
        testID={testID ? `${testID}.retry` : undefined}
      >
        <AppText style={s.retryText}>Try again</AppText>
      </Pressable>
    </View>
  );
}

const s = StyleSheet.create({
  container: {
    alignItems: "center",
    padding: theme.spacing.xxl,
    gap: theme.spacing.lg,
  },
  icon: { opacity: 0.6, marginBottom: theme.spacing.xs },
  message: {
    fontSize: theme.typography.subhead.fontSize,
    color: theme.colors.textSecondary,
    textAlign: "center",
    lineHeight: 22,
  },
  retryBtn: {
    borderWidth: 1,
    borderColor: theme.colors.primary,
    borderRadius: theme.radius.sm,
    paddingHorizontal: theme.spacing.xl,
    paddingVertical: theme.spacing.md,
    minHeight: 44,
    justifyContent: "center",
    marginTop: theme.spacing.sm,
  },
  retryBtnPressed: {
    backgroundColor: theme.colors.primaryLight,
  },
  retryText: {
    color: theme.colors.primary,
    fontWeight: theme.typography.headline.fontWeight as "600",
  },
});
