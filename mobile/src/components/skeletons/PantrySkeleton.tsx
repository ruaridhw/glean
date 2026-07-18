import { StyleSheet, View } from "react-native";
import { theme } from "@/theme";
import { SkeletonBox } from "./SkeletonBox";

export function PantrySkeleton() {
  return (
    <View testID="pantry.skeleton" style={styles.container}>
      {Array.from({ length: 2 }, (_, section) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton never reorders
        <View key={section} style={styles.section}>
          <View style={styles.sectionHeader}>
            <SkeletonBox width={26} height={26} style={styles.chip} />
            <SkeletonBox width="35%" height={12} />
          </View>
          {Array.from({ length: 3 }, (_, row) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: static skeleton never reorders
            <SkeletonBox key={row} width="100%" height={64} style={styles.card} />
          ))}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingTop: theme.spacing.md,
    gap: theme.spacing.lg,
  },
  section: {
    gap: theme.spacing.sm,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.sm,
    marginBottom: theme.spacing.xs,
  },
  chip: {
    borderRadius: theme.radius.sm,
  },
  card: {
    borderRadius: theme.radius.lg,
  },
});
