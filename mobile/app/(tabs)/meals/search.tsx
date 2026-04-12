import { router } from "expo-router";
import { useState } from "react";
import {
  Alert,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { apiClient } from "@/api/client";
import { useRecipeSearch } from "@/api/hooks";
import type { RecipeOut } from "@/api/types";
import { MealsSkeleton } from "@/components/skeletons/MealsSkeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { getRecipeByExternalId, saveRecipe } from "@/db/recipes";
import { theme } from "@/theme";
import { showSuccess } from "@/utils/toast";

export default function SearchScreen() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");

  const { data, isLoading, isError, refetch } = useRecipeSearch(submittedQuery);
  const results = data?.results ?? [];

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
      const detail = await apiClient.get<RecipeOut>(`/recipes/${result.external_id}`);
      const id = await saveRecipe({ ...detail, ingredients: detail.ingredients ?? [] });
      showSuccess("Recipe saved");
      router.push(`/(tabs)/meals/${id}`);
    } catch {
      Alert.alert("Failed to fetch recipe details.");
    }
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      style={s.keyboardView}
    >
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
            autoFocus
          />
          <Pressable style={s.searchBtn} onPress={handleSearch}>
            <Text style={s.searchBtnText}>Go</Text>
          </Pressable>
        </View>

        {isLoading ? (
          <MealsSkeleton />
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
            keyboardDismissMode="on-drag"
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
