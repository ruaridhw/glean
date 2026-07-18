// mobile/app/(tabs)/pantry/add.tsx

import { router } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { AppText } from "@/components/ui/AppText";
import { theme } from "@/theme";

export default function AddScreen() {
  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <AppText style={styles.heading}>Add to Pantry</AppText>
      <Pressable style={styles.option} onPress={() => router.push("/(tabs)/pantry/scan")}>
        <AppText style={styles.icon}>🧾</AppText>
        <View>
          <AppText style={styles.label}>Scan Receipt</AppText>
          <AppText style={styles.sub}>Take a photo of your receipt</AppText>
        </View>
      </Pressable>
      <Pressable style={styles.option} onPress={() => router.push("/(tabs)/pantry/describe")}>
        <AppText style={styles.icon}>💬</AppText>
        <View>
          <AppText style={styles.label}>Describe Purchase</AppText>
          <AppText style={styles.sub}>Type what you bought</AppText>
        </View>
      </Pressable>
      <Pressable style={styles.option} onPress={() => router.push("/(tabs)/pantry/manual-entry")}>
        <AppText style={styles.icon}>✏️</AppText>
        <View>
          <AppText style={styles.label}>Manual Entry</AppText>
          <AppText style={styles.sub}>Add a single item</AppText>
        </View>
      </Pressable>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: theme.spacing.xl, backgroundColor: theme.colors.background },
  heading: {
    ...theme.typography.title2,
    color: theme.colors.text,
    marginBottom: theme.spacing.xl,
  },
  option: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.lg,
    padding: theme.spacing.lg,
    backgroundColor: theme.colors.card,
    borderRadius: theme.radius.lg,
    marginBottom: theme.spacing.md,
    ...theme.shadow.card,
  },
  icon: { fontSize: 28 },
  label: {
    fontSize: 16,
    fontFamily: theme.fontFamily.bold,
    fontWeight: "700",
    color: theme.colors.text,
    marginBottom: 2,
  },
  sub: {
    fontSize: 13,
    fontFamily: theme.fontFamily.semibold,
    fontWeight: "600",
    color: theme.colors.textSecondary,
  },
});
