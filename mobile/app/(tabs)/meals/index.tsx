import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { MealsSkeleton } from "@/components/skeletons/MealsSkeleton";
import { AppScreen } from "@/components/ui/AppScreen";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconButton } from "@/components/ui/IconButton";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { getSavedRecipes } from "@/db/recipes";
import { getRecipeMeta, getRecipeTags } from "@/meals/presentation";
import { theme } from "@/theme";
import type { Recipe } from "@/types";

type MealsTab = "saved" | "search";

function RecipeCard({ recipe }: { recipe: Recipe }) {
  const meta = getRecipeMeta(recipe);
  const tags = getRecipeTags(recipe);

  return (
    <Pressable
      accessibilityRole="button"
      onPress={() => router.push(`/(tabs)/meals/${recipe.id}`)}
      style={styles.cardPressable}
    >
      <Card style={styles.recipeCard}>
        <View style={styles.cardHeader}>
          <Text style={styles.recipeTitle} numberOfLines={2}>
            {recipe.title}
          </Text>
          <Ionicons name="chevron-forward" size={18} color={theme.colors.textDisabled} />
        </View>

        {meta.length > 0 ? (
          <View style={styles.metaRow}>
            {meta.map((item) => (
              <View key={item.label} style={styles.metaItem}>
                <Ionicons name={item.icon} size={14} color={theme.colors.mutedForeground} />
                <Text style={styles.metaText}>{item.label}</Text>
              </View>
            ))}
          </View>
        ) : null}

        {tags.length > 0 ? (
          <View style={styles.tagsRow}>
            {tags.map((tag) => (
              <Badge key={tag} label={tag} />
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
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const result = await getSavedRecipes();
    setRecipes(result);
    setLoading(false);
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const actions = (
    <IconButton
      icon="search-outline"
      accessibilityLabel="Search recipes"
      color={theme.colors.primaryForeground}
      backgroundColor={theme.colors.primary}
      onPress={() => router.push("/(tabs)/meals/search")}
    />
  );

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

  if (loading) {
    return (
      <AppScreen title="Meals" actions={actions} testID="meals.screen">
        {segment}
        <MealsSkeleton />
      </AppScreen>
    );
  }

  if (tab === "search") {
    return (
      <AppScreen
        title="Meals"
        subtitle={`${recipes.length} saved ${recipes.length === 1 ? "recipe" : "recipes"}`}
        actions={actions}
        testID="meals.screen"
      >
        {segment}
        <View style={styles.actionGrid}>
          <Card style={styles.actionCard}>
            <Ionicons name="search-outline" size={24} color={theme.colors.primary} />
            <Text style={styles.actionTitle}>Discover Recipes</Text>
            <Text style={styles.actionText}>Search for recipes and save the ones you like.</Text>
            <Pressable style={styles.primaryAction} onPress={() => router.push("/(tabs)/meals/search")}>
              <Text style={styles.primaryActionText}>Search recipes</Text>
            </Pressable>
          </Card>
          <Card style={styles.actionCard}>
            <Ionicons name="link-outline" size={24} color={theme.colors.primary} />
            <Text style={styles.actionTitle}>Import from URL</Text>
            <Text style={styles.actionText}>Paste a recipe link and Glean will parse it.</Text>
            <Pressable
              style={styles.secondaryAction}
              onPress={() => router.push("/(tabs)/meals/import")}
            >
              <Text style={styles.secondaryActionText}>Import from URL</Text>
            </Pressable>
          </Card>
        </View>
      </AppScreen>
    );
  }

  return (
    <AppScreen
      title="Meals"
      subtitle={`${recipes.length} saved ${recipes.length === 1 ? "recipe" : "recipes"}`}
      actions={actions}
      testID="meals.screen"
    >
      <FlatList
        data={recipes}
        keyExtractor={(recipe) => String(recipe.id)}
        ListHeaderComponent={segment}
        ListHeaderComponentStyle={styles.listHeader}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        renderItem={({ item }) => <RecipeCard recipe={item} />}
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
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  listHeader: {
    marginBottom: theme.spacing.md,
  },
  listContent: {
    paddingBottom: theme.spacing.xl,
  },
  cardPressable: {
    marginBottom: theme.spacing.md,
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
    fontSize: 18,
    fontWeight: "700",
    lineHeight: 24,
  },
  metaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.md,
  },
  metaItem: {
    alignItems: "center",
    flexDirection: "row",
    gap: theme.spacing.xs,
  },
  metaText: {
    color: theme.colors.mutedForeground,
    fontSize: theme.typography.caption.fontSize,
  },
  tagsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.xs,
  },
  actionGrid: {
    gap: theme.spacing.md,
    marginTop: theme.spacing.md,
  },
  actionCard: {
    gap: theme.spacing.sm,
  },
  actionTitle: {
    color: theme.colors.text,
    fontSize: theme.typography.headline.fontSize,
    fontWeight: theme.typography.headline.fontWeight,
  },
  actionText: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.subhead.fontSize,
    lineHeight: 21,
  },
  primaryAction: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.md,
    marginTop: theme.spacing.xs,
    padding: theme.spacing.md,
  },
  primaryActionText: {
    color: theme.colors.primaryForeground,
    fontWeight: "700",
  },
  secondaryAction: {
    alignItems: "center",
    backgroundColor: theme.colors.muted,
    borderRadius: theme.radius.md,
    marginTop: theme.spacing.xs,
    padding: theme.spacing.md,
  },
  secondaryActionText: {
    color: theme.colors.text,
    fontWeight: "700",
  },
});
