import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { getRecipeById, getRecipeIngredients } from "@/db/recipes";
import { theme } from "@/theme";
import type { Recipe, RecipeIngredient } from "@/types";

export default function RecipeDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [ingredients, setIngredients] = useState<RecipeIngredient[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const r = await getRecipeById(Number(id));
      if (!r) {
        router.back();
        return;
      }
      setRecipe(r);
      setIngredients(await getRecipeIngredients(Number(id)));
      setLoading(false);
    }
    load();
  }, [id]);

  if (loading) return <ActivityIndicator style={{ flex: 1 }} />;
  if (!recipe) return null;

  const instructions =
    typeof recipe.instructions === "string" ? JSON.parse(recipe.instructions) : recipe.instructions;

  return (
    <SafeAreaView style={s.container} edges={["top"]}>
      <ScrollView contentContainerStyle={s.content}>
        <Text style={s.title}>{recipe.title}</Text>
        <Text style={s.meta}>
          {[
            recipe.cuisine,
            recipe.difficulty,
            recipe.total_time_mins ? `${recipe.total_time_mins} min` : null,
          ]
            .filter(Boolean)
            .join(" · ")}
        </Text>
        {(recipe.dietary_flags?.length ?? 0) > 0 && (
          <View style={s.flags}>
            {recipe.dietary_flags?.map((f) => (
              <View key={f} style={s.flag}>
                <Text style={s.flagText}>{f}</Text>
              </View>
            ))}
          </View>
        )}

        <Text style={s.sectionHeading}>Ingredients</Text>
        {ingredients.map((ing) => (
          <Text key={ing.id} style={s.ingredient}>
            • {ing.quantity}
            {ing.unit} {ing.ingredient?.canonical_name ?? ""}
            {ing.preparation ? `, ${ing.preparation}` : ""}
            {ing.is_optional ? " (optional)" : ""}
          </Text>
        ))}

        <Text style={s.sectionHeading}>Instructions</Text>
        {instructions.map((step: { step_number: number; phase: string; text: string }) => (
          <View key={step.step_number} style={s.step}>
            <Text style={s.stepNum}>{step.step_number}</Text>
            <Text style={s.stepText}>{step.text}</Text>
          </View>
        ))}

        <Pressable
          style={s.addBtn}
          onPress={() => router.push({ pathname: "/(tabs)/plan", params: { add_recipe_id: id } })}
        >
          <Text style={s.addBtnText}>Add to Plan</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.background },
  content: { padding: theme.spacing.lg },
  title: {
    fontSize: theme.typography.title2.fontSize,
    fontWeight: theme.typography.title2.fontWeight,
    color: theme.colors.text,
    marginBottom: theme.spacing.xs,
  },
  meta: {
    fontSize: theme.typography.caption.fontSize,
    color: theme.colors.textSecondary,
    marginBottom: theme.spacing.md,
  },
  flags: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.xs,
    marginBottom: theme.spacing.lg,
  },
  flag: {
    backgroundColor: theme.colors.primaryLight,
    borderRadius: theme.radius.pill,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: 3,
  },
  flagText: { fontSize: 11, color: theme.colors.primary },
  sectionHeading: {
    fontSize: theme.typography.headline.fontSize,
    fontWeight: theme.typography.headline.fontWeight,
    color: theme.colors.text,
    marginTop: theme.spacing.xl,
    marginBottom: theme.spacing.md,
  },
  ingredient: {
    fontSize: theme.typography.subhead.fontSize,
    marginBottom: theme.spacing.xs,
    color: theme.colors.text,
  },
  step: { flexDirection: "row", marginBottom: theme.spacing.md, gap: theme.spacing.md },
  stepNum: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: theme.colors.primary,
    color: theme.colors.card,
    textAlign: "center",
    lineHeight: 24,
    fontWeight: "700",
    fontSize: 12,
  },
  stepText: {
    flex: 1,
    fontSize: theme.typography.subhead.fontSize,
    lineHeight: 20,
    color: theme.colors.text,
  },
  addBtn: {
    marginTop: theme.spacing.xl,
    marginBottom: theme.spacing.xxl,
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    alignItems: "center",
  },
  addBtnText: {
    color: theme.colors.card,
    fontWeight: "600",
    fontSize: theme.typography.body.fontSize,
  },
});
