import { router } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { apiClient } from "@/api/client";
import type { SaveRecipeParams } from "@/db/recipes";
import { saveRecipe } from "@/db/recipes";
import { theme } from "@/theme";

type RecipeDetailResponse = SaveRecipeParams;

export default function ImportScreen() {
  const [url, setUrl] = useState("");
  const [importing, setImporting] = useState(false);

  async function importFromUrl() {
    if (!url.trim()) return;
    setImporting(true);
    try {
      const detail = await apiClient.post<RecipeDetailResponse>("/recipes/import-url", {
        url: url.trim(),
      });
      const id = await saveRecipe({ ...detail, ingredients: detail.ingredients ?? [] });
      router.push(`/(tabs)/meals/${id}`);
    } catch {
      Alert.alert("Import failed", "Could not parse the recipe. Try a different URL.");
    } finally {
      setImporting(false);
    }
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      style={s.keyboardView}
    >
      <SafeAreaView style={s.container} edges={["top"]}>
        <Text style={s.heading}>Import from URL</Text>
        <Text style={s.subtitle}>Paste a recipe URL and we'll extract the details</Text>
        <TextInput
          style={s.input}
          value={url}
          onChangeText={setUrl}
          placeholder="https://..."
          autoFocus
          autoCapitalize="none"
          keyboardType="url"
          returnKeyType="go"
          onSubmitEditing={importFromUrl}
          placeholderTextColor={theme.colors.textDisabled}
        />
        <Pressable style={s.button} onPress={importFromUrl} disabled={importing || !url.trim()}>
          {importing ? (
            <ActivityIndicator color={theme.colors.card} />
          ) : (
            <Text style={s.buttonText}>Import</Text>
          )}
        </Pressable>
      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  keyboardView: { flex: 1, backgroundColor: theme.colors.background },
  container: { flex: 1, padding: theme.spacing.lg },
  heading: {
    fontSize: theme.typography.title2.fontSize,
    fontWeight: theme.typography.title2.fontWeight,
    color: theme.colors.text,
    marginBottom: theme.spacing.xs,
  },
  subtitle: {
    fontSize: theme.typography.subhead.fontSize,
    color: theme.colors.textSecondary,
    marginBottom: theme.spacing.xl,
  },
  input: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.sm,
    padding: theme.spacing.md,
    fontSize: theme.typography.body.fontSize,
    color: theme.colors.text,
    backgroundColor: theme.colors.card,
    marginBottom: theme.spacing.md,
  },
  button: {
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    alignItems: "center",
  },
  buttonText: {
    color: theme.colors.card,
    fontWeight: "600",
    fontSize: theme.typography.body.fontSize,
  },
});
