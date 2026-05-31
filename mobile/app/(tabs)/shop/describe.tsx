import { router } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput } from "react-native";
import { useParseShoppingDescription } from "@/api/hooks";
import { AppScreen } from "@/components/ui/AppScreen";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { toRequiredSubmittedText } from "@/normalization/text-input";
import { theme } from "@/theme";

export default function ShoppingDescribeScreen() {
  const [text, setText] = useState("");
  const parseMutation = useParseShoppingDescription();

  function parse() {
    const description = toRequiredSubmittedText(text);
    if (!description || parseMutation.isPending) return;

    parseMutation.mutate(
      { text: description },
      {
        onSuccess: (result) => {
          router.push({
            pathname: "/(tabs)/shop/review",
            params: {
              items: JSON.stringify(result.items),
              clarifyingQuestions: JSON.stringify(result.clarifying_questions),
            },
          });
        },
      },
    );
  }

  const canSubmit = Boolean(toRequiredSubmittedText(text));

  return (
    <AppScreen
      title="Describe list"
      subtitle="Type what you need now. Dictation can feed the same text later."
      testID="shopping.describe.screen"
      keyboardAvoiding
    >
      <Card style={styles.card}>
        <TextInput
          style={styles.input}
          value={text}
          onChangeText={setText}
          placeholder="Stuff for tacos, milk, bananas, and lunchbox snacks"
          placeholderTextColor={theme.colors.textDisabled}
          multiline
          autoFocus
        />
        {parseMutation.isError ? (
          <ErrorState
            testID="shopping.describe.error"
            message='Could not turn that into a list. Try being more specific, e.g. "milk, bananas, taco shells".'
            onRetry={() => parseMutation.reset()}
          />
        ) : null}
        <Pressable
          style={[styles.button, (!canSubmit || parseMutation.isPending) && styles.buttonDisabled]}
          onPress={parse}
          disabled={parseMutation.isPending || !canSubmit}
        >
          {parseMutation.isPending ? (
            <ActivityIndicator color={theme.colors.primaryForeground} />
          ) : (
            <Text style={styles.buttonText}>Review items</Text>
          )}
        </Pressable>
      </Card>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  card: {
    gap: theme.spacing.md,
  },
  input: {
    backgroundColor: theme.colors.muted,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    color: theme.colors.text,
    fontSize: theme.typography.subhead.fontSize,
    minHeight: 132,
    padding: theme.spacing.md,
    textAlignVertical: "top",
  },
  button: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.md,
    justifyContent: "center",
    minHeight: 48,
    padding: theme.spacing.md,
  },
  buttonDisabled: { opacity: 0.5 },
  buttonText: {
    color: theme.colors.primaryForeground,
    fontWeight: "700",
  },
});
