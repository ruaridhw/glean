import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { MealsSkeleton } from "@/components/skeletons/MealsSkeleton";
import { AppScreen } from "@/components/ui/AppScreen";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { getSavedRecipes } from "@/db/recipes";
import {
  formatPantryMatch,
  getPantryMatchesForRecipes,
  type PantryMatch,
} from "@/meals/pantry-match";
import { getRecipeTags } from "@/meals/presentation";
import { theme } from "@/theme";
import type { Recipe } from "@/types";

type MealsTab = "saved" | "search";

function RecipeCard({ recipe, match }: { recipe: Recipe; match: PantryMatch | undefined }) {
  const tags = getRecipeTags(recipe);
  const showMatch = match !== undefined && match.m > 0;

  return (
    <Pressable accessibilityRole="button" onPress={() => router.push(`/(tabs)/meals/${recipe.id}`)}>
      <Card style={styles.recipeCard}>
        <View style={styles.cardHeader}>
          <Text style={styles.recipeTitle} numberOfLines={2}>
            {recipe.title}
          </Text>
          <Ionicons name="chevron-forward" size={18} color={theme.colors.textDisabled} />
        </View>

        {recipe.total_time_mins || showMatch ? (
          <View style={styles.metaRow}>
            {recipe.total_time_mins ? (
              <View style={styles.metaItem}>
                <Ionicons name="time-outline" size={14} color={theme.colors.mutedForeground} />
                <Text style={styles.metaText}>{recipe.total_time_mins} min</Text>
              </View>
            ) : null}
            {showMatch ? (
              <View style={styles.metaItem}>
                <Ionicons name="leaf-outline" size={14} color={theme.colors.primaryDark} />
                <Text style={styles.matchText}>{formatPantryMatch(match)}</Text>
              </View>
            ) : null}
          </View>
        ) : null}

        {tags.length > 0 ? (
          <View style={styles.tagsRow}>
            {tags.map((tag) => (
              <Badge key={tag} label={tag} tone="neutral" />
            ))}
          </View>
        ) : null}
      </Card>
    </Pressable>
  );
}

export default function MealsScreen() {
  const [tab, setTab] = useState<MealsTab>("saved");
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [matches, setMatches] = useState<Map<number, PantryMatch>>(new Map());
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const result = await getSavedRecipes();
    setRecipes(result);
    // Pantry match is an enhancement — never let it block the list.
    try {
      setMatches(await getPantryMatchesForRecipes(result.map((recipe) => recipe.id)));
    } catch {
      setMatches(new Map());
    }
    setLoading(false);
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const chips = [{ label: `${recipes.length} saved`, tone: "primary" as const }];

  const segment = (
    <SegmentedControl<MealsTab>
      value={tab}
      onChange={setTab}
      options={[
        { value: "saved", label: `Saved (${recipes.length})`, icon: "bookmark" },
        { value: "search", label: "Search", icon: "search-outline" },
      ]}
    />
  );

  let content: React.ReactNode;
  if (loading) {
    content = <MealsSkeleton />;
  } else if (tab === "search") {
    content = (
      <View style={styles.searchTab}>
        <Pressable
          accessibilityRole="button"
          style={styles.searchPill}
          onPress={() => router.push("/(tabs)/meals/search")}
        >
          <Ionicons name="search-outline" size={18} color={theme.colors.textDisabled} />
          <Text style={styles.searchPillText}>Search recipes…</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          style={styles.importRow}
          onPress={() => router.push("/(tabs)/meals/import")}
        >
          <Ionicons name="link-outline" size={18} color={theme.colors.primary} />
          <Text style={styles.importText}>Paste a recipe URL — Glean will import it</Text>
          <Text style={styles.importAction}>Import</Text>
        </Pressable>
      </View>
    );
  } else {
    content = (
      <FlatList
        data={recipes}
        keyExtractor={(recipe) => String(recipe.id)}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        renderItem={({ item }) => <RecipeCard recipe={item} match={matches.get(item.id)} />}
        ListEmptyComponent={
          <EmptyState
            testID="meals.emptyState"
            icon="restaurant-outline"
            title="No saved recipes"
            message="Search for recipes or import one from a URL."
            actions={[
              { label: "Search recipes", onPress: () => router.push("/(tabs)/meals/search") },
              { label: "Import from URL", onPress: () => router.push("/(tabs)/meals/import") },
            ]}
          />
        }
      />
    );
  }

  return (
    <AppScreen title="Meals" chips={chips} testID="meals.screen">
      <View style={styles.segmentWrap}>{segment}</View>
      {content}
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  segmentWrap: {
    marginBottom: theme.spacing.md,
  },
  listContent: {
    paddingBottom: theme.spacing.xl,
    gap: theme.spacing.md,
  },
  recipeCard: {
    gap: theme.spacing.sm,
  },
  cardHeader: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: theme.spacing.sm,
    justifyContent: "space-between",
  },
  recipeTitle: {
    color: theme.colors.text,
    flex: 1,
    fontSize: 17,
    fontWeight: "800",
    fontFamily: theme.fontFamily.extrabold,
    lineHeight: 22,
  },
  metaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.md,
  },
  metaItem: {
    alignItems: "center",
    flexDirection: "row",
    gap: 5,
  },
  metaText: {
    color: theme.colors.mutedForeground,
    fontSize: 12.5,
    fontWeight: "600",
    fontFamily: theme.fontFamily.semibold,
  },
  matchText: {
    color: theme.colors.primaryDark,
    fontSize: 12.5,
    fontWeight: "700",
    fontFamily: theme.fontFamily.bold,
  },
  tagsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  searchTab: {
    gap: theme.spacing.md,
  },
  searchPill: {
    alignItems: "center",
    backgroundColor: theme.colors.card,
    borderRadius: theme.radius.pill,
    flexDirection: "row",
    gap: theme.spacing.sm,
    paddingHorizontal: 18,
    paddingVertical: 14,
    ...theme.shadow.card,
  },
  searchPillText: {
    color: theme.colors.textDisabled,
    fontSize: 14,
    fontWeight: "600",
    fontFamily: theme.fontFamily.semibold,
  },
  importRow: {
    alignItems: "center",
    backgroundColor: theme.colors.card,
    borderColor: theme.colors.borderStrong,
    borderRadius: theme.radius.lg,
    borderStyle: "dashed",
    borderWidth: 1.5,
    flexDirection: "row",
    gap: theme.spacing.sm,
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: theme.spacing.lg,
  },
  importText: {
    color: theme.colors.mutedForeground,
    flex: 1,
    fontSize: 13.5,
    fontWeight: "700",
    fontFamily: theme.fontFamily.bold,
  },
  importAction: {
    color: theme.colors.primaryDark,
    fontSize: 13,
    fontWeight: "800",
    fontFamily: theme.fontFamily.extrabold,
  },
});
