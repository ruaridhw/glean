// mobile/app/(tabs)/pantry/describe.tsx

import { router } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useDescribeReceipt } from "@/api/hooks";
import { ErrorState } from "@/components/ui/ErrorState";
import { toRequiredSubmittedText } from "@/normalization/text-input";

export default function DescribeScreen() {
  const [text, setText] = useState("");
  const describeMutation = useDescribeReceipt();

  function parse() {
    const description = toRequiredSubmittedText(text);
    if (!description || describeMutation.isPending) return;
    describeMutation.mutate(description, {
      onSuccess: (result) => {
        router.push({
          pathname: "/(tabs)/pantry/review",
          params: { items: JSON.stringify(result.items) },
        });
      },
    });
  }

  const canSubmit = Boolean(toRequiredSubmittedText(text));

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      style={styles.keyboardView}
    >
      <SafeAreaView style={styles.container} edges={["top"]}>
        <Text style={styles.heading}>Describe your shop</Text>
        <Text style={styles.subtitle}>
          e.g. "I bought a kilo of mince and two tins of tomatoes"
        </Text>
        <TextInput
          style={styles.input}
          value={text}
          onChangeText={setText}
          placeholder="What did you buy?"
          multiline
          autoFocus
        />
        {describeMutation.isError && (
          <ErrorState
            testID="describe.error"
            message='Could not understand that. Try being more specific, e.g. "500g chicken breast, 2 tins tomatoes".'
            onRetry={() => describeMutation.reset()}
          />
        )}
        <Pressable
          style={styles.button}
          onPress={parse}
          disabled={describeMutation.isPending || !canSubmit}
        >
          {describeMutation.isPending ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>Parse →</Text>
          )}
        </Pressable>
      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  keyboardView: { flex: 1, backgroundColor: "#fff" },
  container: { flex: 1, padding: 24 },
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
