import { StyleSheet, View } from "react-native";
import { theme } from "@/theme";
import { SkeletonBox } from "./SkeletonBox";

interface PlanSkeletonProps {
  rows?: number;
}

export function PlanSkeleton({ rows = 5 }: PlanSkeletonProps) {
  return (
    <View testID="plan.skeleton" style={styles.container}>
      <View style={styles.progress}>
        <SkeletonBox width={56} height={56} style={styles.ring} />
        <View style={styles.progressText}>
          <SkeletonBox width="55%" height={16} />
          <SkeletonBox width="80%" height={12} />
        </View>
      </View>
      {Array.from({ length: rows }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton rows never reorder
        <View key={i} testID="plan.skeleton.row" style={styles.row}>
          <SkeletonBox width={30} height={30} style={styles.circle} />
          <SkeletonBox width="55%" height={16} />
          <View style={styles.spacer} />
          <SkeletonBox width={72} height={32} style={styles.pill} />
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: theme.spacing.sm,
    paddingTop: theme.spacing.sm,
  },
  progress: {
    alignItems: "center",
    backgroundColor: theme.colors.card,
    borderRadius: theme.radius.lg,
    flexDirection: "row",
    gap: theme.spacing.lg,
    marginBottom: theme.spacing.md,
    padding: theme.spacing.lg,
    ...theme.shadow.card,
  },
  ring: {
    borderRadius: 28,
  },
  progressText: {
    flex: 1,
    gap: theme.spacing.sm,
  },
  row: {
    alignItems: "center",
    backgroundColor: theme.colors.card,
    borderRadius: theme.radius.lg,
    flexDirection: "row",
    gap: theme.spacing.md,
    padding: theme.spacing.lg,
    ...theme.shadow.card,
  },
  circle: {
    borderRadius: 15,
  },
  spacer: {
    flex: 1,
  },
  pill: {
    borderRadius: theme.radius.pill,
  },
});
