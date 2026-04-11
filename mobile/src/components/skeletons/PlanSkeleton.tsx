import { StyleSheet, View } from "react-native";
import { theme } from "@/theme";
import { SkeletonBox } from "./SkeletonBox";

interface PlanSkeletonProps {
  rows?: number;
}

export function PlanSkeleton({ rows = 5 }: PlanSkeletonProps) {
  return (
    <View testID="plan.skeleton" style={styles.container}>
      {Array.from({ length: rows }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton rows never reorder
        <View key={i} testID="plan.skeleton.row" style={styles.row}>
          <SkeletonBox width="60%" height={16} />
          <SkeletonBox width={60} height={28} style={styles.btnPlaceholder} />
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: theme.spacing.lg,
    gap: theme.spacing.md,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: theme.spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.border,
  },
  btnPlaceholder: {
    borderRadius: theme.radius.sm,
  },
});
