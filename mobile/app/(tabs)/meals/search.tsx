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
import { apiClient } from "@/api/client";
import type { SaveRecipeParams } from "@/db/recipes";
import { getRecipeByExternalId, saveRecipe } from "@/db/recipes";
import { theme } from "@/theme";

/** API response shape for recipe detail — matches SaveRecipeParams. */
type RecipeDetailResponse = SaveRecipeParams;

interface SearchResult {
  external_id: string;
  title: string;
  cuisine: string | null;
  difficulty: string | null;
  total_time_mins: number | null;
  dietary_flags: string[];
}

export default function SearchScreen() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [importUrl, setImportUrl] = useState("https://");
  const [importing, setImporting] = useState(false);

  async function search() {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await apiClient.get<{ results: SearchResult[] }>(
        `/recipes/search?q=${encodeURIComponent(query)}`,
      );
      setResults(data.results);
    } catch {
      Alert.alert("Search failed");
    } finally {
      setLoading(false);
    }
  }

  async function addRecipe(result: SearchResult) {
    const cached = await getRecipeByExternalId(result.external_id);
    if (cached) {
      router.push(`/(tabs)/meals/${cached.id}`);
      return;
    }
    try {
      const detail = await apiClient.get<RecipeDetailResponse>(`/recipes/${result.external_id}`);
      const id = await saveRecipe({ ...detail, ingredients: detail.ingredients ?? [] });
      router.push(`/(tabs)/meals/${id}`);
    } catch {
      Alert.alert("Failed to fetch recipe details.");
    }
  }

  function handleImportUrlChange(text: string) {
    if (text.startsWith("https://https://")) {
      setImportUrl(`https://${text.slice("https://https://".length)}`);
    } else if (text.startsWith("http://https://")) {
      setImportUrl(`https://${text.slice("http://https://".length)}`);
    } else {
      setImportUrl(text);
    }
  }

  async function importFromUrl() {
    if (!importUrl.trim()) return;
    setImporting(true);
    try {
      const detail = await apiClient.post<RecipeDetailResponse>("/recipes/import-url", {
        url: importUrl.trim(),
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
    <View style={s.container}>
      <Text style={s.heading}>Discover Recipes</Text>

      <View style={s.searchRow}>
        <TextInput
          style={s.searchInput}
          value={query}
          onChangeText={setQuery}
          placeholder="Search recipes…"
          returnKeyType="search"
          onSubmitEditing={search}
          placeholderTextColor={theme.colors.textDisabled}
        />
        <Pressable style={s.searchBtn} onPress={search}>
          <Text style={s.searchBtnText}>Go</Text>
        </Pressable>
      </View>

      {loading ? (
        <ActivityIndicator style={{ marginTop: theme.spacing.xl }} color={theme.colors.primary} />
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
          onChangeText={handleImportUrlChange}
          autoCapitalize="none"
          keyboardType="url"
          placeholderTextColor={theme.colors.textDisabled}
        />
        <Pressable style={s.importBtn} onPress={importFromUrl} disabled={importing}>
          {importing ? (
            <ActivityIndicator color={theme.colors.card} />
          ) : (
            <Text style={s.importBtnText}>Import</Text>
          )}
        </Pressable>
      </View>
    </View>
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
  importSection: {
    borderTopWidth: 1,
    borderColor: theme.colors.border,
    paddingTop: theme.spacing.lg,
    marginTop: theme.spacing.sm,
  },
  importLabel: {
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "600",
    marginBottom: theme.spacing.sm,
    color: theme.colors.text,
  },
  importInput: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.sm,
    padding: theme.spacing.md,
    fontSize: theme.typography.subhead.fontSize,
    marginBottom: theme.spacing.sm,
    color: theme.colors.text,
    backgroundColor: theme.colors.card,
  },
  importBtn: {
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.sm,
    padding: theme.spacing.md,
    alignItems: "center",
  },
  importBtnText: { color: theme.colors.card, fontWeight: "600" },
});
