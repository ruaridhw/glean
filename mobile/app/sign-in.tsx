// mobile/app/sign-in.tsx

import { router } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { signIn, signUp } from "@/auth/cognito";

type Mode = "sign-in" | "sign-up";

export default function SignInScreen() {
  const [mode, setMode] = useState<Mode>("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    if (!email.trim() || !password.trim()) return;
    setLoading(true);
    try {
      if (mode === "sign-in") {
        await signIn(email.trim(), password);
        router.replace("/(tabs)/pantry");
      } else {
        await signUp(email.trim(), password);
        Alert.alert("Account created", "Check your email for a verification code, then sign in.");
        setMode("sign-in");
      }
    } catch (e) {
      Alert.alert(
        mode === "sign-in" ? "Sign in failed" : "Sign up failed",
        e instanceof Error ? e.message : "Unknown error",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Glean</Text>
      <Text style={styles.subtitle}>Waste less. Cook better.</Text>
      <View style={styles.modeRow}>
        <Pressable
          onPress={() => setMode("sign-in")}
          style={[styles.modeBtn, mode === "sign-in" && styles.modeBtnActive]}
        >
          <Text style={[styles.modeBtnText, mode === "sign-in" && styles.modeBtnTextActive]}>
            Sign in
          </Text>
        </Pressable>
        <Pressable
          onPress={() => setMode("sign-up")}
          style={[styles.modeBtn, mode === "sign-up" && styles.modeBtnActive]}
        >
          <Text style={[styles.modeBtnText, mode === "sign-up" && styles.modeBtnTextActive]}>
            Create account
          </Text>
        </Pressable>
      </View>
      <TextInput
        style={styles.input}
        value={email}
        onChangeText={setEmail}
        placeholder="Email"
        keyboardType="email-address"
        autoCapitalize="none"
        autoCorrect={false}
      />
      <TextInput
        style={styles.input}
        value={password}
        onChangeText={setPassword}
        placeholder="Password"
        secureTextEntry
      />
      <Pressable style={styles.button} onPress={handleSubmit} disabled={loading}>
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>{mode === "sign-in" ? "Sign in" : "Create account"}</Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", padding: 24, backgroundColor: "#fff" },
  title: {
    fontSize: 32,
    fontWeight: "800",
    color: "#2a9d8f",
    textAlign: "center",
    marginBottom: 4,
  },
  subtitle: { fontSize: 16, color: "#888", textAlign: "center", marginBottom: 32 },
  modeRow: {
    flexDirection: "row",
    marginBottom: 24,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#ddd",
    overflow: "hidden",
  },
  modeBtn: { flex: 1, padding: 10, alignItems: "center" },
  modeBtnActive: { backgroundColor: "#2a9d8f" },
  modeBtnText: { color: "#888", fontWeight: "600" },
  modeBtnTextActive: { color: "#fff" },
  input: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    marginBottom: 12,
  },
  button: { backgroundColor: "#2a9d8f", borderRadius: 8, padding: 14, alignItems: "center" },
  buttonText: { color: "#fff", fontWeight: "600", fontSize: 16 },
});
