import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { AppScreen } from "@/components/ui/AppScreen";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { IconButton } from "@/components/ui/IconButton";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatsRow } from "@/components/ui/StatsRow";
import { getRecipeById, getRecipeIngredients } from "@/db/recipes";
import { formatRecipeIngredient, getRecipeTags, parseInstructionSteps } from "@/meals/presentation";
import { theme } from "@/theme";
import type { Recipe, RecipeIngredient } from "@/types";

export default function RecipeDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [ingredients, setIngredients] = useState<RecipeIngredient[]>([]);
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
      setLoading(false);
    }
    void load();
  }, [id]);

  const actions = (
    <IconButton
      icon="chevron-back"
      accessibilityLabel="Back to meals"
      backgroundColor={theme.colors.muted}
      onPress={() => router.back()}
    />
  );

  if (loading) {
    return (
      <AppScreen title="Recipe" actions={actions} testID="recipe.detail">
        <View style={styles.loading}>
          <ActivityIndicator color={theme.colors.primary} />
        </View>
      </AppScreen>
    );
  }

  if (!recipe) return null;

  const tags = getRecipeTags(recipe);
  const instructions = parseInstructionSteps(recipe.instructions);

  return (
    <AppScreen title="Recipe" actions={actions} scroll testID="recipe.detail">
      <Card style={styles.heroCard}>
        <Text style={styles.title}>{recipe.title}</Text>
        {tags.length > 0 ? (
          <View style={styles.tagsRow}>
            {tags.map((tag) => (
              <Badge key={tag} label={tag} />
            ))}
          </View>
        ) : null}
      </Card>

      <StatsRow
        style={styles.stats}
        stats={[
          { value: recipe.total_time_mins ? `${recipe.total_time_mins} min` : "-", label: "Total" },
          {
            value: recipe.active_time_mins ? `${recipe.active_time_mins} min` : "-",
            label: "Active",
          },
          { value: recipe.yield_count ? `${recipe.yield_count} servings` : "-", label: "Serves" },
        ]}
      />

      <SectionHeader title="Ingredients" />
      <Card style={styles.sectionCard}>
        {ingredients.map((ingredient, index) => (
          <View key={ingredient.id} style={[styles.ingredientRow, index > 0 && styles.dividedRow]}>
            <View style={styles.dot} />
            <Text style={styles.ingredientText}>{formatRecipeIngredient(ingredient)}</Text>
          </View>
        ))}
      </Card>

      <SectionHeader title="Instructions" />
      <Card style={styles.sectionCard}>
        {instructions.map((step, index) => (
          <View
            key={`${step.number}-${step.text}`}
            style={[styles.stepRow, index > 0 && styles.stepGap]}
          >
            <View style={styles.stepNumber}>
              <Text style={styles.stepNumberText}>{step.number}</Text>
            </View>
            <Text style={styles.stepText}>{step.text}</Text>
          </View>
        ))}
      </Card>

      <Pressable
        accessibilityRole="button"
        style={styles.addButton}
        onPress={() => router.push({ pathname: "/(tabs)/plan", params: { add_recipe_id: id } })}
      >
        <Ionicons name="calendar-outline" size={18} color={theme.colors.primaryForeground} />
        <Text style={styles.addButtonText}>Add to Plan</Text>
      </Pressable>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  loading: {
    alignItems: "center",
    flex: 1,
    justifyContent: "center",
  },
  heroCard: {
    gap: theme.spacing.md,
  },
  title: {
    color: theme.colors.text,
    fontSize: 26,
    fontWeight: "800",
    lineHeight: 32,
  },
  tagsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.xs,
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
    gap: theme.spacing.sm,
    paddingVertical: theme.spacing.xs,
  },
  dividedRow: {
    borderColor: theme.colors.border,
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingTop: theme.spacing.sm,
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
    fontSize: theme.typography.subhead.fontSize,
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
    fontSize: theme.typography.caption.fontSize,
    fontWeight: "700",
  },
  stepText: {
    color: theme.colors.text,
    flex: 1,
    fontSize: theme.typography.subhead.fontSize,
    lineHeight: 22,
  },
  addButton: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.md,
    flexDirection: "row",
    gap: theme.spacing.sm,
    justifyContent: "center",
    marginTop: theme.spacing.xl,
    padding: theme.spacing.md,
  },
  addButtonText: {
    color: theme.colors.primaryForeground,
    fontSize: theme.typography.body.fontSize,
    fontWeight: "700",
  },
});
