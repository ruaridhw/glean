import { StyleSheet, View } from "react-native";
import { theme } from "@/theme";
import { SkeletonBox } from "./SkeletonBox";

export function ShoppingSkeleton() {
  return (
    <View testID="shop.skeleton" style={styles.container}>
      {Array.from({ length: 6 }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton rows never reorder
        <View key={i} style={styles.row}>
          <SkeletonBox width={24} height={24} style={styles.checkbox} />
          <SkeletonBox width="65%" height={15} />
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
  checkbox: {
    borderRadius: theme.spacing.xs,
  },
});
