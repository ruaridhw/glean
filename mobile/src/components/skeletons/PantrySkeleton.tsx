import { StyleSheet, View } from "react-native";
import { theme } from "@/theme";
import { SkeletonBox } from "./SkeletonBox";

export function PantrySkeleton() {
  return (
    <View testID="pantry.skeleton" style={styles.container}>
      {Array.from({ length: 5 }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton rows never reorder
        <View key={i} style={styles.row}>
          <SkeletonBox width={20} height={20} style={styles.circle} />
          <SkeletonBox width="70%" height={15} />
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
    gap: theme.spacing.md,
  },
  circle: {
    borderRadius: 10,
  },
});
