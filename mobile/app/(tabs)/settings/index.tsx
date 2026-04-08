// mobile/app/(tabs)/settings/index.tsx

import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { signOut } from "@/auth/cognito";
import { theme } from "@/theme";

export default function SettingsScreen() {
  async function handleSignOut() {
    await signOut();
    router.replace("/sign-in");
  }

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Settings</Text>
      <Pressable style={styles.button} onPress={handleSignOut}>
        <Text style={styles.buttonText}>Sign out</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: theme.spacing.lg, backgroundColor: theme.colors.background },
  heading: {
    fontSize: theme.typography.title2.fontSize,
    fontWeight: theme.typography.title2.fontWeight,
    color: theme.colors.text,
    marginBottom: theme.spacing.xxl,
  },
  button: {
    backgroundColor: theme.colors.warning,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    alignItems: "center",
  },
  buttonText: { color: theme.colors.card, fontWeight: "600", fontSize: 16 },
});
