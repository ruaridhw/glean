import { StyleSheet, Text, View, type ViewProps } from "react-native";
import { theme } from "@/theme";

type BadgeTone = "neutral" | "primary" | "warning" | "danger";

interface BadgeProps extends ViewProps {
  label: string;
  tone?: BadgeTone;
}

const toneStyles: Record<BadgeTone, { backgroundColor: string; color: string }> = {
  neutral: { backgroundColor: theme.colors.muted, color: theme.colors.mutedForeground },
  primary: { backgroundColor: theme.colors.primary, color: theme.colors.primaryForeground },
  warning: { backgroundColor: theme.colors.warning, color: theme.colors.primaryForeground },
  danger: { backgroundColor: theme.colors.danger, color: theme.colors.primaryForeground },
};

export function Badge({ label, tone = "neutral", style, ...props }: BadgeProps) {
  const colors = toneStyles[tone];
  return (
    <View style={[styles.badge, { backgroundColor: colors.backgroundColor }, style]} {...props}>
      <Text style={[styles.text, { color: colors.color }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: "flex-start",
    borderRadius: theme.radius.pill,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: 3,
  },
  text: { fontSize: theme.typography.caption.fontSize, fontWeight: "700" },
});
