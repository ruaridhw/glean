// mobile/app/(tabs)/pantry/describe.tsx

import { router } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useDescribeReceipt } from "@/api/hooks";
import { AppText } from "@/components/ui/AppText";
import { AppTextInput } from "@/components/ui/AppTextInput";
import { ErrorState } from "@/components/ui/ErrorState";
import { serializeReviewItems } from "@/intake/serialization";
import { toRequiredSubmittedText } from "@/normalization/text-input";
import { theme } from "@/theme";

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
          params: { items: serializeReviewItems(result.items) },
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
        <AppText style={styles.heading}>Describe your shop</AppText>
        <AppText style={styles.subtitle}>
          e.g. "I bought a kilo of mince and two tins of tomatoes"
        </AppText>
        <AppTextInput
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
            <ActivityIndicator color={theme.colors.primaryForeground} />
          ) : (
            <AppText style={styles.buttonText}>Parse →</AppText>
          )}
        </Pressable>
      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  keyboardView: { flex: 1, backgroundColor: theme.colors.background },
  container: { flex: 1, padding: theme.spacing.xl },
  heading: {
    ...theme.typography.title2,
    color: theme.colors.text,
    marginBottom: theme.spacing.sm,
  },
  subtitle: {
    fontSize: 14,
    fontFamily: theme.fontFamily.semibold,
    fontWeight: "600",
    color: theme.colors.textSecondary,
    marginBottom: 20,
  },
  input: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    fontSize: 16,
    fontFamily: theme.fontFamily.regular,
    color: theme.colors.text,
    backgroundColor: theme.colors.card,
    minHeight: 100,
    textAlignVertical: "top",
    marginBottom: theme.spacing.lg,
  },
  button: {
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.pill,
    padding: 14,
    alignItems: "center",
    minHeight: 44,
    justifyContent: "center",
    ...theme.shadow.fab,
  },
  buttonText: {
    color: theme.colors.primaryForeground,
    fontFamily: theme.fontFamily.extrabold,
    fontWeight: "800",
    fontSize: 16,
  },
});
