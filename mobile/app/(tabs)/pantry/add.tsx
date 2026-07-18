// mobile/app/(tabs)/pantry/add.tsx

import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { theme } from "@/theme";

export default function AddScreen() {
  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <Text style={styles.heading}>Add to Pantry</Text>
      <Pressable style={styles.option} onPress={() => router.push("/(tabs)/pantry/scan")}>
        <Text style={styles.icon}>🧾</Text>
        <View>
          <Text style={styles.label}>Scan Receipt</Text>
          <Text style={styles.sub}>Take a photo of your receipt</Text>
        </View>
      </Pressable>
      <Pressable style={styles.option} onPress={() => router.push("/(tabs)/pantry/describe")}>
        <Text style={styles.icon}>💬</Text>
        <View>
          <Text style={styles.label}>Describe Purchase</Text>
          <Text style={styles.sub}>Type what you bought</Text>
        </View>
      </Pressable>
      <Pressable style={styles.option} onPress={() => router.push("/(tabs)/pantry/manual-entry")}>
        <Text style={styles.icon}>✏️</Text>
        <View>
          <Text style={styles.label}>Manual Entry</Text>
          <Text style={styles.sub}>Add a single item</Text>
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
