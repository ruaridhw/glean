// mobile/app/(tabs)/pantry/add.tsx

import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

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
  container: { flex: 1, padding: 24, backgroundColor: "#fff" },
  heading: { fontSize: 22, fontWeight: "700", marginBottom: 24 },
  option: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: "#eee",
    borderRadius: 12,
    marginBottom: 12,
  },
  icon: { fontSize: 28 },
  label: { fontSize: 16, fontWeight: "600", marginBottom: 2 },
  sub: { fontSize: 13, color: "#888" },
});
