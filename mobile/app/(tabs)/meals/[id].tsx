import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { AppText } from "@/components/ui/AppText";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatsRow } from "@/components/ui/StatsRow";
import { getRecipeById, getRecipeIngredients } from "@/db/recipes";
import { getPantryIngredientIds } from "@/meals/pantry-match";
import { formatRecipeIngredient, getRecipeTags, parseInstructionSteps } from "@/meals/presentation";
import { theme } from "@/theme";
import type { Recipe, RecipeIngredient } from "@/types";

export default function RecipeDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [ingredients, setIngredients] = useState<RecipeIngredient[]>([]);
  // null = pantry state unavailable → hide in-pantry/to-buy chips (graceful degrade).
  const [pantryIds, setPantryIds] = useState<Set<number> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const fetchedRecipe = await getRecipeById(Number(id));
      if (!fetchedRecipe) {
        router.back();
        return;
      }
      const fetchedIngredients = await getRecipeIngredients(Number(id));
      setRecipe(fetchedRecipe);
      setIngredients(fetchedIngredients);
      try {
        setPantryIds(await getPantryIngredientIds());
      } catch {
        setPantryIds(null);
      }
      setLoading(false);
    }
    void load();
  }, [id]);

  const header = (
    <View style={styles.header}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Back to meals"
        style={styles.headerButton}
        onPress={() => router.back()}
      >
        <Ionicons name="chevron-back" size={20} color={theme.colors.ink} />
      </Pressable>
      <AppText style={styles.headerTitle}>Recipe</AppText>
      <View style={styles.headerButton}>
        <Ionicons name="bookmark" size={18} color={theme.colors.ink} />
      </View>
    </View>
  );

  if (loading || !recipe) {
    return (
      <SafeAreaView style={styles.container} edges={["top"]} testID="recipe.detail">
        {header}
        <View style={styles.loading}>
          <ActivityIndicator color={theme.colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  const tags = getRecipeTags(recipe);
  const instructions = parseInstructionSteps(recipe.instructions);

  return (
    <SafeAreaView style={styles.container} edges={["top"]} testID="recipe.detail">
      {header}
      <ScrollView
        contentContainerStyle={[styles.scroll, { paddingBottom: insets.bottom + 96 }]}
        showsVerticalScrollIndicator={false}
      >
        <Card style={styles.heroCard}>
          <AppText style={styles.title}>{recipe.title}</AppText>
          {tags.length > 0 ? (
            <View style={styles.tagsRow}>
              {tags.map((tag) => (
                <Badge key={tag} label={tag} tone="primary" />
              ))}
            </View>
          ) : null}
        </Card>

        <StatsRow
          style={styles.stats}
          stats={[
            {
              value: recipe.total_time_mins ? `${recipe.total_time_mins} min` : "—",
              label: "Total",
            },
            {
              value: recipe.active_time_mins ? `${recipe.active_time_mins} min` : "—",
              label: "Active",
            },
            { value: recipe.yield_count ? `${recipe.yield_count}` : "—", label: "Serves" },
          ]}
        />

        <SectionHeader title="Ingredients" />
        <Card style={styles.sectionCard}>
          {ingredients.map((ingredient, index) => {
            const inPantry =
              pantryIds !== null &&
              ingredient.ingredient_id != null &&
              pantryIds.has(ingredient.ingredient_id);
            return (
              <View
                key={ingredient.id}
                style={[styles.ingredientRow, index < ingredients.length - 1 && styles.dividedRow]}
              >
                <View style={styles.dot} />
                <AppText style={styles.ingredientText}>
                  {formatRecipeIngredient(ingredient)}
                </AppText>
                {pantryIds !== null ? (
                  <Badge
                    label={inPantry ? "in pantry" : "to buy"}
                    tone={inPantry ? "primary" : "warning"}
                  />
                ) : null}
              </View>
            );
          })}
        </Card>

        <SectionHeader title="Instructions" />
        <Card style={styles.sectionCard}>
          {instructions.map((step, index) => (
            <View
              key={`${step.number}-${step.text}`}
              style={[styles.stepRow, index > 0 && styles.stepGap]}
            >
              <View style={styles.stepNumber}>
                <AppText style={styles.stepNumberText}>{step.number}</AppText>
              </View>
              <AppText style={styles.stepText}>{step.text}</AppText>
            </View>
          ))}
        </Card>

        <Pressable
          accessibilityRole="button"
          style={styles.addButton}
          onPress={() => router.push({ pathname: "/(tabs)/plan", params: { add_recipe_id: id } })}
        >
          <Ionicons name="calendar-outline" size={18} color={theme.colors.primaryForeground} />
          <AppText style={styles.addButtonText}>Add to plan</AppText>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  header: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: theme.spacing.lg,
    paddingTop: theme.spacing.lg,
    paddingBottom: theme.spacing.md,
  },
  headerButton: {
    alignItems: "center",
    backgroundColor: theme.colors.muted,
    borderRadius: theme.radius.pill,
    height: 40,
    justifyContent: "center",
    width: 40,
  },
  headerTitle: {
    ...theme.typography.sectionLabel,
  },
  loading: {
    alignItems: "center",
    flex: 1,
    justifyContent: "center",
  },
  scroll: {
    paddingHorizontal: theme.spacing.lg,
  },
  heroCard: {
    gap: theme.spacing.md,
  },
  title: {
    color: theme.colors.text,
    fontSize: 25,
    fontWeight: "800",
    fontFamily: theme.fontFamily.extrabold,
    letterSpacing: -0.5,
    lineHeight: 31,
  },
  tagsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  stats: {
    marginTop: theme.spacing.md,
  },
  sectionCard: {
    gap: theme.spacing.sm,
  },
  ingredientRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: 10,
    paddingVertical: 7,
  },
  dividedRow: {
    borderColor: theme.colors.border,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  dot: {
    backgroundColor: theme.colors.primary,
    borderRadius: 3,
    height: 6,
    width: 6,
  },
  ingredientText: {
    color: theme.colors.text,
    flex: 1,
    fontSize: 14.5,
    fontWeight: "600",
    fontFamily: theme.fontFamily.semibold,
  },
  stepRow: {
    flexDirection: "row",
    gap: theme.spacing.md,
  },
  stepGap: {
    marginTop: theme.spacing.md,
  },
  stepNumber: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: 13,
    height: 26,
    justifyContent: "center",
    width: 26,
  },
  stepNumberText: {
    color: theme.colors.primaryForeground,
    fontSize: 12,
    fontWeight: "800",
    fontFamily: theme.fontFamily.extrabold,
  },
  stepText: {
    color: theme.colors.text,
    flex: 1,
    fontSize: 14.5,
    fontWeight: "500",
    fontFamily: theme.fontFamily.medium,
    lineHeight: 22,
  },
  addButton: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.pill,
    flexDirection: "row",
    gap: theme.spacing.sm,
    justifyContent: "center",
    marginTop: theme.spacing.xl,
    padding: 15,
    ...theme.shadow.fab,
  },
  addButtonText: {
    color: theme.colors.primaryForeground,
    fontSize: 15,
    fontWeight: "800",
    fontFamily: theme.fontFamily.extrabold,
  },
});
