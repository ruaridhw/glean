import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { theme } from "@/theme";

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  actionLabel?: string;
  onAction?: () => void;
  /** Optional leading tinted icon chip (e.g. pantry category sections). */
  icon?: keyof typeof Ionicons.glyphMap;
  iconColor?: string;
  iconBackground?: string;
  /** Optional trailing count shown at the end of the row. */
  count?: number | string;
  testID?: string;
}

export function SectionHeader({
  title,
  subtitle,
  actionLabel,
  onAction,
  icon,
  iconColor,
  iconBackground,
  count,
  testID,
}: SectionHeaderProps) {
  return (
    <View style={styles.container} testID={testID}>
      <View style={styles.leading}>
        {icon ? (
          <View
            style={[styles.iconChip, iconBackground ? { backgroundColor: iconBackground } : null]}
          >
            <Ionicons name={icon} size={15} color={iconColor ?? theme.colors.mutedForeground} />
          </View>
        ) : null}
        <View style={styles.textGroup}>
          <Text style={styles.title}>{title}</Text>
          {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
        </View>
      </View>
      {actionLabel && onAction ? (
        <Pressable accessibilityRole="button" onPress={onAction} hitSlop={8}>
          <Text style={styles.action}>{actionLabel}</Text>
        </Pressable>
      ) : count !== undefined ? (
        <Text style={styles.count}>{count}</Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: theme.spacing.sm,
    marginTop: theme.spacing.lg,
  },
  leading: {
    alignItems: "center",
    flex: 1,
    flexDirection: "row",
    gap: theme.spacing.sm,
  },
  iconChip: {
    alignItems: "center",
    backgroundColor: theme.colors.muted,
    borderRadius: theme.radius.sm,
    height: 26,
    justifyContent: "center",
    width: 26,
  },
  textGroup: { flex: 1 },
  title: {
    ...theme.typography.sectionLabel,
  },
  subtitle: {
    color: theme.colors.mutedForeground,
    fontSize: theme.typography.caption.fontSize,
    fontFamily: theme.fontFamily.semibold,
    marginTop: 2,
  },
  action: {
    color: theme.colors.primaryDark,
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "700",
    fontFamily: theme.fontFamily.bold,
  },
  count: {
    color: theme.colors.textDisabled,
    fontSize: 12,
    fontWeight: "800",
    fontFamily: theme.fontFamily.extrabold,
  },
});
