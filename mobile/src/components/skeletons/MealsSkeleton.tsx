import { StyleSheet, View } from "react-native";
import { theme } from "@/theme";
import { SkeletonBox } from "./SkeletonBox";

export function MealsSkeleton() {
  return (
    <View testID="meals.skeleton" style={styles.container}>
      {Array.from({ length: 4 }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton rows never reorder
        <View key={i} style={styles.row}>
          <SkeletonBox width="100%" height={15} />
          <SkeletonBox width="60%" height={12} />
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: theme.spacing.lg,
    gap: theme.spacing.lg,
  },
  row: {
    gap: theme.spacing.sm,
  },
});
