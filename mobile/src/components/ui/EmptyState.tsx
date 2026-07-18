import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, View } from "react-native";
import { theme } from "@/theme";
import { AppText } from "./AppText";

interface EmptyStateAction {
  label: string;
  onPress: () => void;
}

interface EmptyStateProps {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  message: string;
  actions?: EmptyStateAction[];
  testID?: string;
}

export function EmptyState({ icon, title, message, actions, testID }: EmptyStateProps) {
  return (
    <View style={s.container} testID={testID}>
      <Ionicons name={icon} size={64} color={theme.colors.textDisabled} style={s.icon} />
      <AppText style={s.title}>{title}</AppText>
      <AppText style={s.message}>{message}</AppText>
      {actions && actions.length > 0 && (
        <View style={s.actions}>
          {actions.map((action) => (
            <Pressable key={action.label} style={s.actionBtn} onPress={action.onPress}>
              <AppText style={s.actionText}>{action.label}</AppText>
            </Pressable>
          ))}
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: theme.spacing.xxl,
  },
  icon: { marginBottom: theme.spacing.xl, opacity: 0.6 },
  title: {
    fontSize: theme.typography.title2.fontSize,
    fontWeight: theme.typography.title2.fontWeight,
    color: theme.colors.text,
    textAlign: "center",
    marginBottom: theme.spacing.sm,
  },
  message: {
    fontSize: theme.typography.subhead.fontSize,
    color: theme.colors.textSecondary,
    textAlign: "center",
    lineHeight: 22,
    marginBottom: theme.spacing.xl,
  },
  actions: { flexDirection: "row", gap: theme.spacing.md },
  actionBtn: {
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.sm,
    paddingHorizontal: theme.spacing.xl,
    paddingVertical: theme.spacing.md,
    minHeight: 44,
    justifyContent: "center",
  },
  actionText: {
    color: theme.colors.card,
    fontWeight: theme.typography.headline.fontWeight as "600",
    fontSize: theme.typography.subhead.fontSize,
  },
});
