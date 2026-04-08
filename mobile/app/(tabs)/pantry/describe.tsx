// mobile/app/(tabs)/pantry/describe.tsx

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
import { apiClient } from "@/api/client";

export default function DescribeScreen() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);

  async function parse() {
    if (!text.trim()) return;
    setLoading(true);
    try {
      const result = await apiClient.post<{ items: unknown[] }>("/receipts/describe", { text });
      router.push({
        pathname: "/(tabs)/pantry/review",
        params: { items: JSON.stringify(result.items) },
      });
    } catch {
      Alert.alert(
        "Parse failed",
        'Could not understand that. Try being more specific, e.g. "500g chicken breast, 2 tins tomatoes".',
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Describe your shop</Text>
      <Text style={styles.subtitle}>e.g. "I bought a kilo of mince and two tins of tomatoes"</Text>
      <TextInput
        style={styles.input}
        value={text}
        onChangeText={setText}
        placeholder="What did you buy?"
        multiline
        autoFocus
      />
      <Pressable style={styles.button} onPress={parse} disabled={loading || !text.trim()}>
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Parse →</Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, backgroundColor: "#fff" },
  heading: { fontSize: 22, fontWeight: "700", marginBottom: 8 },
  subtitle: { fontSize: 14, color: "#888", marginBottom: 20 },
  input: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    minHeight: 100,
    textAlignVertical: "top",
    marginBottom: 16,
  },
  button: { backgroundColor: "#2a9d8f", borderRadius: 8, padding: 14, alignItems: "center" },
  buttonText: { color: "#fff", fontWeight: "600", fontSize: 16 },
});
