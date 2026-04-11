import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { theme } from "@/theme";

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
      <Ionicons name="alert-circle-outline" size={48} color={theme.colors.warning} />
      <Text style={s.message}>{message}</Text>
      <Pressable
        style={s.retryBtn}
        onPress={onRetry}
        testID={testID ? `${testID}.retry` : undefined}
      >
        <Text style={s.retryText}>Try again</Text>
      </Pressable>
    </View>
  );
}

const s = StyleSheet.create({
  container: {
    alignItems: "center",
    padding: theme.spacing.xxl,
    gap: theme.spacing.md,
  },
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
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: theme.spacing.sm,
    marginTop: theme.spacing.sm,
  },
  retryText: {
    color: theme.colors.primary,
    fontWeight: theme.typography.headline.fontWeight as "600",
  },
});
