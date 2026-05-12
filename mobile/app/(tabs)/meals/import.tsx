import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, Text, TextInput } from "react-native";
import { apiClient } from "@/api/client";
import { AppScreen } from "@/components/ui/AppScreen";
import { Card } from "@/components/ui/Card";
import type { SaveRecipeParams } from "@/db/recipes";
import { saveRecipe } from "@/db/recipes";
import { theme } from "@/theme";

type RecipeDetailResponse = SaveRecipeParams;

export default function ImportScreen() {
  const [url, setUrl] = useState("");
  const [importing, setImporting] = useState(false);

  function handleUrlChange(text: string) {
    if (text.startsWith("https://https://")) {
      setUrl(`https://${text.slice("https://https://".length)}`);
    } else if (text.startsWith("http://https://")) {
      setUrl(`https://${text.slice("http://https://".length)}`);
    } else {
      setUrl(text);
    }
  }

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
    <AppScreen
      title="Import from URL"
      subtitle="Paste a recipe link"
      keyboardAvoiding
      testID="meals.import"
    >
      <Card style={styles.card}>
        <Ionicons name="link-outline" size={28} color={theme.colors.primary} />
        <Text style={styles.title}>Recipe link</Text>
        <Text style={styles.subtitle}>Paste a recipe URL and Glean will extract the details.</Text>
        <TextInput
          style={styles.input}
          value={url}
          onChangeText={handleUrlChange}
          placeholder="https://..."
          autoFocus
          autoCapitalize="none"
          keyboardType="url"
          returnKeyType="go"
          onSubmitEditing={importFromUrl}
          placeholderTextColor={theme.colors.textDisabled}
        />
        <Pressable
          style={[styles.button, (importing || !url.trim()) && styles.buttonDisabled]}
          onPress={importFromUrl}
          disabled={importing || !url.trim()}
        >
          {importing ? (
            <ActivityIndicator color={theme.colors.primaryForeground} />
          ) : (
            <Text style={styles.buttonText}>Import</Text>
          )}
        </Pressable>
      </Card>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  card: {
    gap: theme.spacing.md,
    marginTop: theme.spacing.md,
  },
  title: {
    color: theme.colors.text,
    fontSize: theme.typography.headline.fontSize,
    fontWeight: "700",
  },
  subtitle: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.subhead.fontSize,
    lineHeight: 21,
  },
  input: {
    backgroundColor: theme.colors.muted,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    color: theme.colors.text,
    fontSize: theme.typography.body.fontSize,
    padding: theme.spacing.md,
  },
  button: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.md,
    minHeight: 48,
    justifyContent: "center",
    padding: theme.spacing.md,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: theme.colors.primaryForeground,
    fontSize: theme.typography.body.fontSize,
    fontWeight: "700",
  },
});
