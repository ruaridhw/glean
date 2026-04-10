import { router } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { apiClient } from "@/api/client";
import { useRecipeSearch, useImportRecipe } from "@/api/hooks";
import { ErrorState } from "@/components/ui/ErrorState";
import type { SaveRecipeParams } from "@/db/recipes";
import { getRecipeByExternalId, saveRecipe } from "@/db/recipes";
import { theme } from "@/theme";
import { showSuccess } from "@/utils/toast";

/** API response shape for recipe detail — matches SaveRecipeParams. */
type RecipeDetailResponse = SaveRecipeParams;

export default function SearchScreen() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [importUrl, setImportUrl] = useState("");

  const { data, isLoading, isError, refetch } = useRecipeSearch(submittedQuery);
  const results = data?.results ?? [];

  const importMutation = useImportRecipe();

  function handleSearch() {
    if (!query.trim()) return;
    setSubmittedQuery(query.trim());
  }

  async function addRecipe(result: { external_id: string }) {
    const cached = await getRecipeByExternalId(result.external_id);
    if (cached) {
      router.push(`/(tabs)/meals/${cached.id}`);
      return;
    }
    try {
      const detail = await apiClient.get<RecipeDetailResponse>(`/recipes/${result.external_id}`);
      const id = await saveRecipe({ ...detail, ingredients: detail.ingredients ?? [] });
      showSuccess("Recipe saved");
      router.push(`/(tabs)/meals/${id}`);
    } catch {
      Alert.alert("Failed to fetch recipe details.");
    }
  }

  async function importFromUrl() {
    if (!importUrl.trim()) return;
    try {
      const detail = await importMutation.mutateAsync(importUrl.trim());
      const id = await saveRecipe({ ...detail, ingredients: detail.ingredients ?? [] });
      showSuccess("Recipe imported");
      router.push(`/(tabs)/meals/${id}`);
    } catch {
      Alert.alert("Import failed", "Could not parse the recipe. Try a different URL.");
    }
  }

  return (
    <SafeAreaView style={s.container} edges={["top"]}>
      <Text style={s.heading}>Discover Recipes</Text>

      <View style={s.searchRow}>
        <TextInput
          style={s.searchInput}
          value={query}
          onChangeText={setQuery}
          placeholder="Search recipes…"
          returnKeyType="search"
          onSubmitEditing={handleSearch}
          placeholderTextColor={theme.colors.textDisabled}
        />
        <Pressable style={s.searchBtn} onPress={handleSearch}>
          <Text style={s.searchBtnText}>Go</Text>
        </Pressable>
      </View>

      {isLoading ? (
        <ActivityIndicator style={{ marginTop: theme.spacing.xl }} color={theme.colors.primary} />
      ) : isError ? (
        <ErrorState
          testID="search.error"
          message="Search failed. Check your connection and try again."
          onRetry={refetch}
        />
      ) : (
        <FlatList
          data={results}
          keyExtractor={(r) => r.external_id}
          renderItem={({ item }) => (
            <Pressable style={s.result} onPress={() => addRecipe(item)}>
              <Text style={s.resultTitle}>{item.title}</Text>
              <Text style={s.resultMeta}>
                {[
                  item.cuisine,
                  item.difficulty,
                  item.total_time_mins ? `${item.total_time_mins}min` : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </Text>
            </Pressable>
          )}
        />
      )}

      <View style={s.importSection}>
        <Text style={s.importLabel}>Import from URL</Text>
        <TextInput
          style={s.importInput}
          value={importUrl}
          onChangeText={setImportUrl}
          placeholder="https://..."
          autoCapitalize="none"
          keyboardType="url"
          placeholderTextColor={theme.colors.textDisabled}
        />
        <Pressable style={s.importBtn} onPress={importFromUrl} disabled={importMutation.isPending}>
          {importMutation.isPending ? (
            <ActivityIndicator color={theme.colors.card} />
          ) : (
            <Text style={s.importBtnText}>Import</Text>
          )}
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.background, padding: theme.spacing.lg },
  heading: {
    fontSize: theme.typography.title2.fontSize,
    fontWeight: theme.typography.title2.fontWeight,
    color: theme.colors.text,
    marginBottom: theme.spacing.lg,
  },
  searchRow: { flexDirection: "row", gap: theme.spacing.sm, marginBottom: theme.spacing.md },
  searchInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.sm,
    padding: theme.spacing.md,
    fontSize: theme.typography.body.fontSize,
    color: theme.colors.text,
    backgroundColor: theme.colors.card,
  },
  searchBtn: {
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.sm,
    paddingHorizontal: theme.spacing.lg,
    justifyContent: "center",
  },
  searchBtnText: { color: theme.colors.card, fontWeight: "600" },
  result: {
    padding: theme.spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.border,
  },
  resultTitle: {
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "600",
    marginBottom: 2,
    color: theme.colors.text,
  },
  resultMeta: { fontSize: theme.typography.caption.fontSize, color: theme.colors.textSecondary },
});
