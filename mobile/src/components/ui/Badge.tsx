import { StyleSheet, View, type ViewProps } from "react-native";
import { theme } from "@/theme";
import { AppText } from "./AppText";

type BadgeTone = "neutral" | "primary" | "warning" | "danger";

interface BadgeProps extends ViewProps {
  label: string;
  tone?: BadgeTone;
  /** Override the tinted background (e.g. category colour pairs). */
  backgroundColor?: string;
  /** Override the text colour. */
  color?: string;
}

// Tinted pairs — soft background + dark foreground.
const toneStyles: Record<BadgeTone, { backgroundColor: string; color: string }> = {
  neutral: { backgroundColor: theme.colors.muted, color: theme.colors.mutedForeground },
  primary: { backgroundColor: theme.colors.primaryLight, color: theme.colors.primaryDark },
  warning: { backgroundColor: theme.colors.warningLight, color: theme.colors.warning },
  danger: { backgroundColor: theme.colors.dangerLight, color: theme.colors.danger },
};

export function Badge({
  label,
  tone = "neutral",
  backgroundColor,
  color,
  style,
  ...props
}: BadgeProps) {
  const colors = toneStyles[tone];
  return (
    <View
      style={[styles.badge, { backgroundColor: backgroundColor ?? colors.backgroundColor }, style]}
      {...props}
    >
      <AppText style={[styles.text, { color: color ?? colors.color }]}>{label}</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: "flex-start",
    borderRadius: theme.radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  text: { fontSize: 12, fontWeight: "700", fontFamily: theme.fontFamily.bold },
});
