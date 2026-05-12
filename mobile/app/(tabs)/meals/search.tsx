import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useState } from "react";
import { Alert, FlatList, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { apiClient } from "@/api/client";
import { useRecipeSearch } from "@/api/hooks";
import type { RecipeOut, RecipeSearchResult } from "@/api/types";
import { MealsSkeleton } from "@/components/skeletons/MealsSkeleton";
import { AppScreen } from "@/components/ui/AppScreen";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { IconButton } from "@/components/ui/IconButton";
import { getRecipeByExternalId, saveRecipe } from "@/db/recipes";
import { theme } from "@/theme";
import { showSuccess } from "@/utils/toast";

function SearchResultCard({ result, onPress }: { result: RecipeSearchResult; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.resultPressable}>
      <Card style={styles.resultCard}>
        <View style={styles.resultHeader}>
          <Text style={styles.resultTitle}>{result.title}</Text>
          <Ionicons name="chevron-forward" size={18} color={theme.colors.textDisabled} />
        </View>
        <View style={styles.badgeRow}>
          {result.cuisine ? <Badge label={result.cuisine} /> : null}
          {result.difficulty ? <Badge label={result.difficulty} /> : null}
          {result.total_time_mins ? <Badge label={`${result.total_time_mins} min`} /> : null}
        </View>
      </Card>
    </Pressable>
  );
}

export default function SearchScreen() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");

  const { data, isLoading, isError, refetch } = useRecipeSearch(submittedQuery);
  const results = data?.results ?? [];

  function handleSearch() {
    if (!query.trim()) return;
    setSubmittedQuery(query.trim());
  }

  async function addRecipe(result: RecipeSearchResult) {
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
    <AppScreen
      title="Discover Recipes"
      subtitle="Find new meals for your plan"
      actions={
        <IconButton
          icon="link-outline"
          accessibilityLabel="Import recipe URL"
          onPress={() => router.push("/(tabs)/meals/import")}
        />
      }
      testID="meals.search"
    >
      <Card style={styles.searchCard}>
        <View style={styles.searchRow}>
          <TextInput
            style={styles.searchInput}
            value={query}
            onChangeText={setQuery}
            placeholder="Search recipes..."
            returnKeyType="search"
            onSubmitEditing={handleSearch}
            placeholderTextColor={theme.colors.textDisabled}
            autoFocus
          />
          <Pressable style={styles.searchBtn} onPress={handleSearch}>
            <Text style={styles.searchBtnText}>Go</Text>
          </Pressable>
        </View>
      </Card>

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
          keyExtractor={(result) => result.external_id}
          keyboardDismissMode="on-drag"
          contentContainerStyle={styles.listContent}
          renderItem={({ item }) => (
            <SearchResultCard result={item} onPress={() => void addRecipe(item)} />
          )}
        />
      )}
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  searchCard: {
    marginBottom: theme.spacing.md,
  },
  searchRow: {
    flexDirection: "row",
    gap: theme.spacing.sm,
  },
  searchInput: {
    backgroundColor: theme.colors.muted,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    color: theme.colors.text,
    flex: 1,
    fontSize: theme.typography.body.fontSize,
    padding: theme.spacing.md,
  },
  searchBtn: {
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.md,
    justifyContent: "center",
    paddingHorizontal: theme.spacing.lg,
  },
  searchBtnText: {
    color: theme.colors.primaryForeground,
    fontWeight: "700",
  },
  listContent: {
    paddingBottom: theme.spacing.xl,
  },
  resultPressable: {
    marginBottom: theme.spacing.md,
  },
  resultCard: {
    gap: theme.spacing.sm,
  },
  resultHeader: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: theme.spacing.sm,
  },
  resultTitle: {
    color: theme.colors.text,
    flex: 1,
    fontSize: theme.typography.headline.fontSize,
    fontWeight: "700",
  },
  badgeRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.xs,
  },
});
