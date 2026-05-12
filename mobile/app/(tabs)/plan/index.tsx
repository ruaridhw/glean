// mobile/app/(tabs)/plan/index.tsx

import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect, useLocalSearchParams } from "expo-router";
import { useCallback, useState } from "react";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { useSuggestMeals } from "@/api/hooks";
import { PlanSkeleton } from "@/components/skeletons/PlanSkeleton";
import { AppScreen } from "@/components/ui/AppScreen";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconButton } from "@/components/ui/IconButton";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { getUserConfig } from "@/db/config";
import { getPantryItems } from "@/db/pantry";
import {
  addMealPlanEntry,
  deleteMealPlanEntry,
  getMealPlanCount,
  getMealPlanEntries,
  markMealAsCooked,
} from "@/db/plan";
import { getSavedRecipes } from "@/db/recipes";
import { addShoppingGapsForRecipe } from "@/db/shopping";
import {
  buildPlanSlots,
  formatPlanProgress,
  getCurrentWeekRangeLabel,
  getPlanSubtitle,
  type PlanSlot,
} from "@/plan/presentation";
import { hapticImpact } from "@/platform/haptics";
import { compressPantry } from "@/suggestions/compress";
import { theme } from "@/theme";
import type { MealPlanEntry } from "@/types";
import { showError, showSuccess } from "@/utils/toast";

function ProgressCard({ planned, target }: { planned: number; target: number }) {
  const progress = formatPlanProgress(planned, target);
  return (
    <Card style={styles.progressCard}>
      <View style={styles.progressHeader}>
        <View>
          <Text style={styles.progressLabel}>Dinner progress</Text>
          <Text style={styles.weekRange}>{getCurrentWeekRangeLabel()}</Text>
        </View>
        <Ionicons name="calendar-outline" size={22} color={theme.colors.primary} />
      </View>
      <View style={styles.progressTrack}>
        <View style={[styles.progressFill, { width: `${progress.percent}%` }]} />
      </View>
    </Card>
  );
}

function PlanSlotCard({
  slot,
  onCooked,
  onDelete,
}: {
  slot: PlanSlot;
  onCooked: (entry: MealPlanEntry) => void;
  onDelete: (entry: MealPlanEntry) => void;
}) {
  const entry = slot.entry;

  if (!entry) {
    return (
      <Pressable
        accessibilityRole="button"
        onPress={() => router.push("/(tabs)/meals/search")}
        style={styles.slotPressable}
      >
        <Card style={[styles.slotCard, styles.emptySlotCard]}>
          <View style={styles.slotBadgeMuted}>
            <Text style={styles.slotBadgeMutedText}>{slot.slotNumber}</Text>
          </View>
          <Text style={styles.addDinnerText}>Add dinner</Text>
          <Ionicons name="add" size={18} color={theme.colors.primary} />
        </Card>
      </Pressable>
    );
  }

  const cooked = entry.cooked_at != null;

  return (
    <Card style={[styles.slotCard, cooked && styles.cookedCard]}>
      <View style={cooked ? styles.slotBadgeMuted : styles.slotBadge}>
        <Text style={cooked ? styles.slotBadgeMutedText : styles.slotBadgeText}>
          {slot.slotNumber}
        </Text>
      </View>
      <View style={styles.slotContent}>
        <Text style={[styles.recipeTitle, cooked && styles.cookedTitle]}>{entry.recipe_title}</Text>
        <Text style={styles.recipeMeta}>
          {entry.servings} {entry.servings === 1 ? "serving" : "servings"}
          {cooked ? " · Cooked" : ""}
        </Text>
      </View>
      {!cooked ? (
        <Pressable style={styles.cookedButton} onPress={() => onCooked(entry)}>
          <Text style={styles.cookedButtonText}>Cooked</Text>
        </Pressable>
      ) : null}
      <IconButton
        icon="close-circle"
        accessibilityLabel={`Remove ${entry.recipe_title}`}
        backgroundColor="transparent"
        color={theme.colors.textSecondary}
        size={20}
        onPress={() => onDelete(entry)}
      />
    </Card>
  );
}

export default function PlanScreen() {
  const [entries, setEntries] = useState<MealPlanEntry[]>([]);
  const [mealsPerWeek, setMealsPerWeek] = useState(5);
  const [loading, setLoading] = useState(true);
  const suggestMutation = useSuggestMeals();
  const { add_recipe_id: addRecipeId } = useLocalSearchParams<{ add_recipe_id?: string }>();

  const load = useCallback(async () => {
    setLoading(true);
    const [fetchedEntries, config] = await Promise.all([getMealPlanEntries(), getUserConfig()]);
    setEntries(fetchedEntries);
    setMealsPerWeek(config.meals_per_week);
    setLoading(false);
  }, []);

  const handleAddRecipe = useCallback(
    async (recipeId: number) => {
      const count = await getMealPlanCount();
      if (count >= mealsPerWeek) {
        Alert.alert("Plan full", `You already have ${mealsPerWeek} meals planned.`);
        return;
      }
      await addMealPlanEntry(recipeId);
      await addShoppingGapsForRecipe(recipeId);
      showSuccess("Meal planned");
      await load();
    },
    [mealsPerWeek, load],
  );

  useFocusEffect(
    useCallback(() => {
      void load();
      if (addRecipeId) {
        void handleAddRecipe(Number(addRecipeId));
      }
    }, [load, addRecipeId, handleAddRecipe]),
  );

  async function handleMarkCooked(entry: MealPlanEntry) {
    await hapticImpact("medium");
    await markMealAsCooked(entry.id);
    await load();
  }

  async function handleDelete(entry: MealPlanEntry) {
    await deleteMealPlanEntry(entry.id);
    await load();
  }

  async function generateWeek() {
    const emptySlots = mealsPerWeek - entries.length;
    if (emptySlots <= 0) {
      Alert.alert("Plan is full", "Remove some meals before generating.");
      return;
    }

    const [pantryItems, recipes, config] = await Promise.all([
      getPantryItems(),
      getSavedRecipes(),
      getUserConfig(),
    ]);

    const compressed = compressPantry(pantryItems as Parameters<typeof compressPantry>[0]);
    const recipeHistory = recipes.map((recipe) => ({
      recipe_id: recipe.id,
      title: recipe.title,
      last_cooked_at: recipe.last_cooked_at ?? null,
      food_groups: [] as string[],
    }));

    suggestMutation.mutate(
      {
        pantry: compressed,
        recipe_history: recipeHistory,
        food_group_coverage: {},
        purchase_tolerance: config.purchase_tolerance,
        meals_per_week: emptySlots,
        dietary_flags: config.dietary_flags,
        max_active_time_mins: config.max_active_time_mins ?? null,
      },
      {
        onSuccess: async (result) => {
          for (const suggestion of result.suggestions.slice(0, emptySlots)) {
            await addMealPlanEntry(suggestion.recipe_id);
            await addShoppingGapsForRecipe(suggestion.recipe_id);
          }
          showSuccess("Week generated");
          await load();
        },
        onError: () => {
          showError("Could not generate suggestions");
        },
      },
    );
  }

  const slots = buildPlanSlots(entries, mealsPerWeek);
  const subtitle = getPlanSubtitle(entries, mealsPerWeek);

  if (loading) {
    return (
      <AppScreen title="This Week" subtitle={subtitle} testID="plan.screen">
        <PlanSkeleton rows={mealsPerWeek} />
      </AppScreen>
    );
  }

  if (entries.length === 0) {
    return (
      <AppScreen
        title="This Week"
        subtitle={subtitle}
        actions={
          <IconButton
            icon="sparkles-outline"
            accessibilityLabel="Generate plan"
            color={theme.colors.primaryForeground}
            backgroundColor={theme.colors.primary}
            onPress={() => void generateWeek()}
          />
        }
        testID="plan.screen"
      >
        <ProgressCard planned={entries.length} target={mealsPerWeek} />
        <EmptyState
          testID="plan.emptyState"
          icon="calendar-outline"
          title="No meals planned this week"
          message="Add recipes to your plan or let AI suggest a week."
          actions={[
            { label: "Browse recipes", onPress: () => router.push("/(tabs)/meals" as never) },
            { label: "Generate plan", onPress: generateWeek },
          ]}
        />
      </AppScreen>
    );
  }

  return (
    <AppScreen
      title="This Week"
      subtitle={subtitle}
      actions={
        <Pressable style={styles.generateButton} onPress={() => void generateWeek()}>
          <Ionicons name="sparkles-outline" size={15} color={theme.colors.primaryForeground} />
          <Text style={styles.generateButtonText}>
            {suggestMutation.isPending ? "Generating" : "Generate plan"}
          </Text>
        </Pressable>
      }
      scroll
      testID="plan.screen"
    >
      <ProgressCard planned={entries.length} target={mealsPerWeek} />
      <SectionHeader title="Dinners" subtitle="Plan meals and send gaps to shopping" />
      <View style={styles.slotList}>
        {slots.map((slot) => (
          <PlanSlotCard
            key={slot.key}
            slot={slot}
            onCooked={(entry) => void handleMarkCooked(entry)}
            onDelete={(entry) => void handleDelete(entry)}
          />
        ))}
      </View>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  progressCard: {
    gap: theme.spacing.md,
  },
  progressHeader: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  progressLabel: {
    color: theme.colors.text,
    fontSize: theme.typography.headline.fontSize,
    fontWeight: "700",
  },
  weekRange: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.caption.fontSize,
    marginTop: 2,
  },
  progressTrack: {
    backgroundColor: theme.colors.muted,
    borderRadius: 2,
    height: 4,
    overflow: "hidden",
  },
  progressFill: {
    backgroundColor: theme.colors.primary,
    borderRadius: 2,
    height: "100%",
  },
  generateButton: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.pill,
    flexDirection: "row",
    gap: theme.spacing.xs,
    minHeight: 40,
    paddingHorizontal: theme.spacing.md,
  },
  generateButtonText: {
    color: theme.colors.primaryForeground,
    fontSize: theme.typography.caption.fontSize,
    fontWeight: "700",
  },
  slotList: {
    gap: theme.spacing.sm,
  },
  slotPressable: {
    marginBottom: theme.spacing.xs,
  },
  slotCard: {
    alignItems: "center",
    flexDirection: "row",
    gap: theme.spacing.md,
  },
  emptySlotCard: {
    borderStyle: "dashed",
  },
  cookedCard: {
    opacity: 0.65,
  },
  slotBadge: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: 14,
    height: 28,
    justifyContent: "center",
    width: 28,
  },
  slotBadgeText: {
    color: theme.colors.primaryForeground,
    fontSize: theme.typography.caption.fontSize,
    fontWeight: "700",
  },
  slotBadgeMuted: {
    alignItems: "center",
    backgroundColor: theme.colors.muted,
    borderRadius: 14,
    height: 28,
    justifyContent: "center",
    width: 28,
  },
  slotBadgeMutedText: {
    color: theme.colors.mutedForeground,
    fontSize: theme.typography.caption.fontSize,
    fontWeight: "700",
  },
  slotContent: {
    flex: 1,
  },
  recipeTitle: {
    color: theme.colors.text,
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "700",
  },
  cookedTitle: {
    textDecorationLine: "line-through",
  },
  recipeMeta: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.caption.fontSize,
    marginTop: 2,
  },
  cookedButton: {
    borderColor: theme.colors.primary,
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
  },
  cookedButtonText: {
    color: theme.colors.primary,
    fontSize: theme.typography.caption.fontSize,
    fontWeight: "700",
  },
  addDinnerText: {
    color: theme.colors.textSecondary,
    flex: 1,
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "600",
  },
});
