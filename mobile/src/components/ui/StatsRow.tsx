import type { ReactNode } from "react";
import { StyleSheet, View, type ViewProps } from "react-native";
import { theme } from "@/theme";
import { AppText } from "./AppText";

interface StatsRowItem {
  value: ReactNode;
  label: string;
}

interface StatsRowProps extends ViewProps {
  stats: StatsRowItem[];
}

export function StatsRow({ stats, style, ...props }: StatsRowProps) {
  return (
    <View style={[styles.container, style]} {...props}>
      {stats.map((stat, index) => (
        <View key={stat.label} style={[styles.stat, index > 0 && styles.statDivider]}>
          {typeof stat.value === "string" || typeof stat.value === "number" ? (
            <AppText style={styles.value}>{stat.value}</AppText>
          ) : (
            stat.value
          )}
          <AppText style={styles.label}>{stat.label}</AppText>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: theme.colors.card,
    borderRadius: theme.radius.lg,
    flexDirection: "row",
    overflow: "hidden",
    ...theme.shadow.card,
  },
  stat: {
    alignItems: "center",
    flex: 1,
    padding: theme.spacing.md,
  },
  statDivider: {
    borderColor: theme.colors.border,
    borderLeftWidth: 1,
  },
  value: {
    color: theme.colors.primary,
    fontSize: 22,
    fontWeight: "800",
    fontFamily: theme.fontFamily.extrabold,
  },
  label: {
    color: theme.colors.mutedForeground,
    fontFamily: theme.fontFamily.semibold,
    fontSize: theme.typography.caption.fontSize,
    marginTop: 2,
    textAlign: "center",
  },
});
