import type { ReactNode } from "react";
import { StyleSheet, Text, View, type ViewProps } from "react-native";
import { theme } from "@/theme";

export interface StatsRowItem {
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
        <View
          key={`${stat.label}-${index}`}
          style={[styles.stat, index > 0 && styles.statDivider]}
        >
          {typeof stat.value === "string" || typeof stat.value === "number" ? (
            <Text style={styles.value}>{stat.value}</Text>
          ) : (
            stat.value
          )}
          <Text style={styles.label}>{stat.label}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: theme.colors.card,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    borderWidth: 1,
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
  },
  label: {
    color: theme.colors.mutedForeground,
    fontSize: theme.typography.caption.fontSize,
    marginTop: 2,
    textAlign: "center",
  },
});
