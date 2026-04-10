import { StyleSheet, View } from "react-native";
import { theme } from "@/theme";
import { SkeletonBox } from "./SkeletonBox";

export function PlanSkeleton() {
  return (
    <View testID="plan.skeleton" style={styles.container}>
      {Array.from({ length: 5 }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton rows never reorder
        <View key={i} style={styles.row}>
          <SkeletonBox width="80%" height={15} />
          <SkeletonBox width={60} height={28} />
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
    gap: theme.spacing.md,
  },
});
