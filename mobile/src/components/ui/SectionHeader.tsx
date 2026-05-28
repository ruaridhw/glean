import { Pressable, StyleSheet, Text, View } from "react-native";
import { theme } from "@/theme";

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  actionLabel?: string;
  onAction?: () => void;
  testID?: string;
}

export function SectionHeader({
  title,
  subtitle,
  actionLabel,
  onAction,
  testID,
}: SectionHeaderProps) {
  return (
    <View style={styles.container} testID={testID}>
      <View style={styles.textGroup}>
        <Text style={styles.title}>{title}</Text>
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      </View>
      {actionLabel && onAction ? (
        <Pressable accessibilityRole="button" onPress={onAction} hitSlop={8}>
          <Text style={styles.action}>{actionLabel}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "flex-end",
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: theme.spacing.sm,
    marginTop: theme.spacing.lg,
  },
  textGroup: { flex: 1 },
  title: {
    ...theme.typography.sectionLabel,
    color: theme.colors.textSecondary,
  },
  subtitle: {
    color: theme.colors.mutedForeground,
    fontSize: theme.typography.caption.fontSize,
    marginTop: 2,
  },
  action: {
    color: theme.colors.primary,
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: theme.typography.headline.fontWeight,
  },
});
