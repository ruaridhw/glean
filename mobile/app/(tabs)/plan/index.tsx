// mobile/app/(tabs)/plan/index.tsx

import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect, useLocalSearchParams } from "expo-router";
import { useCallback, useRef, useState } from "react";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Circle } from "react-native-svg";
import { useGenerateMealPlan } from "@/api/hooks";
import { PlanSkeleton } from "@/components/skeletons/PlanSkeleton";
import { SwipeDeleteRow } from "@/components/swipe-delete-row";
import { AppScreen } from "@/components/ui/AppScreen";
import { Card } from "@/components/ui/Card";
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
import { compressPantry } from "@/meal-plan/compress";
import {
  buildPlanSlots,
  getCurrentWeekRangeLabel,
  getPlanExpiryNudge,
  getPlanHint,
  getPlanRingModel,
  type PlanExpiryNudge,
  type PlanSlot,
} from "@/plan/presentation";
import { hapticImpact } from "@/platform/haptics";
import { theme } from "@/theme";
import type { MealPlanEntry, PantryItem } from "@/types";
import { showError, showSuccess } from "@/utils/toast";

function ProgressCard({ planned, target }: { planned: number; target: number }) {
  const ring = getPlanRingModel(planned, target);
  return (
    <Card style={styles.progressCard}>
      <View style={styles.ring}>
        <Svg width={ring.size} height={ring.size} viewBox={`0 0 ${ring.size} ${ring.size}`}>
          <Circle
            cx={ring.center}
            cy={ring.center}
            r={ring.radius}
            fill="none"
            stroke={theme.colors.muted}
            strokeWidth={ring.strokeWidth}
          />
          <Circle
            cx={ring.center}
            cy={ring.center}
            r={ring.radius}
            fill="none"
            stroke={theme.colors.primary}
            strokeWidth={ring.strokeWidth}
            strokeLinecap="round"
            strokeDasharray={ring.dashArray}
            transform={`rotate(-90 ${ring.center} ${ring.center})`}
          />
        </Svg>
        <Text style={styles.ringLabel}>{ring.ratioLabel}</Text>
      </View>
      <View style={styles.progressText}>
        <Text style={styles.progressTitle}>Dinner progress</Text>
        <Text style={styles.progressHint}>{getPlanHint(planned, target)}</Text>
      </View>
    </Card>
  );
}

function ExpiryNudgeBanner({ nudge }: { nudge: PlanExpiryNudge }) {
  return (
    <View style={styles.nudge} testID="plan.expiryNudge">
      <View style={styles.nudgeIcon}>
        <Ionicons name="time-outline" size={16} color={theme.colors.warning} />
      </View>
      <View style={styles.nudgeText}>
        <Text style={styles.nudgeTitle}>{nudge.title}</Text>
        <Text style={styles.nudgeMessage}>{nudge.message}</Text>
      </View>
    </View>
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
        style={styles.emptySlot}
      >
        <View style={styles.slotCircleMuted}>
          <Text style={styles.slotCircleMutedText}>{slot.slotNumber}</Text>
        </View>
        <Text style={styles.addDinnerText}>Add a dinner</Text>
        <Ionicons name="add" size={20} color={theme.colors.primary} />
      </Pressable>
    );
  }

  const cooked = entry.cooked_at != null;

  return (
    <SwipeDeleteRow
      actionTestID={`plan-slot-delete-action-${entry.id}`}
      iconTestID={`plan-slot-delete-icon-${entry.id}`}
      rowTestID={`plan-slot-row-${entry.id}`}
      onDelete={() => onDelete(entry)}
    >
      {(deleteActive) => (
        <Card style={styles.slotCard}>
          {cooked ? (
            <View style={styles.slotCircleCooked}>
              <Ionicons name="checkmark" size={16} color={theme.colors.primaryDark} />
            </View>
          ) : (
            <View style={styles.slotCircle}>
              <Text style={styles.slotCircleText}>{slot.slotNumber}</Text>
            </View>
          )}
          <View style={styles.slotContent}>
            <Text style={[styles.recipeTitle, cooked && styles.cookedTitle]}>
              {entry.recipe_title}
            </Text>
            <Text style={styles.recipeMeta}>
              {entry.servings} {entry.servings === 1 ? "serving" : "servings"}
              {cooked ? " · Cooked" : ""}
            </Text>
          </View>
          {!cooked ? (
            <Pressable style={styles.cookedButton} onPress={() => onCooked(entry)}>
              <Text style={styles.cookedButtonText}>Cooked?</Text>
            </Pressable>
          ) : null}
          <IconButton
            icon="close-circle"
            accessibilityLabel={`Remove ${entry.recipe_title}`}
            backgroundColor={deleteActive ? theme.colors.dangerLight : "transparent"}
            color={deleteActive ? theme.colors.danger : theme.colors.textDisabled}
            size={20}
            onPress={() => onDelete(entry)}
          />
        </Card>
      )}
    </SwipeDeleteRow>
  );
}

export default function PlanScreen() {
  const [entries, setEntries] = useState<MealPlanEntry[]>([]);
  const [pantryItems, setPantryItems] = useState<PantryItem[]>([]);
  const [mealsPerWeek, setMealsPerWeek] = useState(5);
  const [loading, setLoading] = useState(true);
  const mealPlanMutation = useGenerateMealPlan();
  const { add_recipe_id: addRecipeId } = useLocalSearchParams<{ add_recipe_id?: string }>();

  const load = useCallback(async () => {
    setLoading(true);
    const [fetchedEntries, config, fetchedPantry] = await Promise.all([
      getMealPlanEntries(),
      getUserConfig(),
      getPantryItems(),
    ]);
    setEntries(fetchedEntries);
    setMealsPerWeek(config.meals_per_week);
    setPantryItems(fetchedPantry);
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
  const handleAddRecipeRef = useRef(handleAddRecipe);
  handleAddRecipeRef.current = handleAddRecipe;

  useFocusEffect(
    useCallback(() => {
      void load();
      if (addRecipeId) {
        void handleAddRecipeRef.current(Number(addRecipeId));
      }
    }, [load, addRecipeId]),
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

    const [pantry, recipes, config] = await Promise.all([
      getPantryItems(),
      getSavedRecipes(),
      getUserConfig(),
    ]);

    const compressed = compressPantry(pantry as Parameters<typeof compressPantry>[0]);
    const recipeHistory = recipes.map((recipe) => ({
      recipe_id: recipe.id,
      title: recipe.title,
      last_cooked_at: recipe.last_cooked_at ?? null,
      food_groups: [] as string[],
    }));

    mealPlanMutation.mutate(
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
          showError("Could not generate meal plan");
        },
      },
    );
  }

  const slots = buildPlanSlots(entries, mealsPerWeek);
  const weekRange = getCurrentWeekRangeLabel();
  const expiryNudge = getPlanExpiryNudge(pantryItems);

  if (loading) {
    return (
      <AppScreen title="This Week" subtitle={weekRange} testID="plan.screen">
        <PlanSkeleton rows={mealsPerWeek} />
      </AppScreen>
    );
  }

  return (
    <AppScreen
      title="This Week"
      subtitle={weekRange}
      actions={
        <Pressable
          accessibilityRole="button"
          style={styles.generateButton}
          onPress={() => void generateWeek()}
        >
          <Ionicons name="sparkles-outline" size={15} color={theme.colors.primaryForeground} />
          <Text style={styles.generateButtonText}>
            {mealPlanMutation.isPending ? "Generating" : "Generate"}
          </Text>
        </Pressable>
      }
      scroll
      testID="plan.screen"
    >
      <ProgressCard planned={entries.length} target={mealsPerWeek} />
      <SectionHeader title="Dinners" />
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
      {expiryNudge ? <ExpiryNudgeBanner nudge={expiryNudge} /> : null}
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  progressCard: {
    alignItems: "center",
    flexDirection: "row",
    gap: theme.spacing.lg,
  },
  ring: {
    alignItems: "center",
    justifyContent: "center",
  },
  ringLabel: {
    ...theme.typography.caption,
    color: theme.colors.text,
    fontFamily: theme.fontFamily.extrabold,
    fontSize: 15,
    fontWeight: "800",
    position: "absolute",
  },
  progressText: {
    flex: 1,
    gap: 2,
  },
  progressTitle: {
    color: theme.colors.text,
    fontFamily: theme.fontFamily.bold,
    fontSize: theme.typography.headline.fontSize,
    fontWeight: "700",
  },
  progressHint: {
    color: theme.colors.textSecondary,
    fontFamily: theme.fontFamily.semibold,
    fontSize: theme.typography.caption.fontSize,
    fontWeight: "600",
  },
  generateButton: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.pill,
    flexDirection: "row",
    gap: theme.spacing.xs,
    minHeight: 44,
    paddingHorizontal: theme.spacing.lg,
    ...theme.shadow.fab,
  },
  generateButtonText: {
    color: theme.colors.primaryForeground,
    fontFamily: theme.fontFamily.extrabold,
    fontSize: 13,
    fontWeight: "800",
  },
  slotList: {
    gap: theme.spacing.sm,
  },
  slotCard: {
    alignItems: "center",
    flexDirection: "row",
    gap: theme.spacing.md,
    paddingVertical: theme.spacing.md,
  },
  slotCircle: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: 15,
    height: 30,
    justifyContent: "center",
    width: 30,
  },
  slotCircleText: {
    color: theme.colors.primaryForeground,
    fontFamily: theme.fontFamily.extrabold,
    fontSize: 13,
    fontWeight: "800",
  },
  slotCircleCooked: {
    alignItems: "center",
    backgroundColor: theme.colors.primaryLight,
    borderRadius: 15,
    height: 30,
    justifyContent: "center",
    width: 30,
  },
  slotCircleMuted: {
    alignItems: "center",
    backgroundColor: theme.colors.muted,
    borderRadius: 15,
    height: 30,
    justifyContent: "center",
    width: 30,
  },
  slotCircleMutedText: {
    color: theme.colors.mutedForeground,
    fontFamily: theme.fontFamily.extrabold,
    fontSize: 13,
    fontWeight: "800",
  },
  slotContent: {
    flex: 1,
  },
  recipeTitle: {
    color: theme.colors.text,
    fontFamily: theme.fontFamily.bold,
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "700",
  },
  cookedTitle: {
    color: theme.colors.textSecondary,
  },
  recipeMeta: {
    color: theme.colors.textDisabled,
    fontFamily: theme.fontFamily.semibold,
    fontSize: theme.typography.caption.fontSize,
    fontWeight: "600",
    marginTop: 2,
  },
  cookedButton: {
    borderColor: theme.colors.primary,
    borderRadius: theme.radius.pill,
    borderWidth: 1.5,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
  },
  cookedButtonText: {
    color: theme.colors.primaryDark,
    fontFamily: theme.fontFamily.extrabold,
    fontSize: 12,
    fontWeight: "800",
  },
  emptySlot: {
    alignItems: "center",
    borderColor: theme.colors.border,
    borderRadius: theme.radius.lg,
    borderStyle: "dashed",
    borderWidth: 1.5,
    flexDirection: "row",
    gap: theme.spacing.md,
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: theme.spacing.md,
  },
  addDinnerText: {
    color: theme.colors.textSecondary,
    flex: 1,
    fontFamily: theme.fontFamily.bold,
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "700",
  },
  nudge: {
    alignItems: "center",
    backgroundColor: theme.colors.warningLight,
    borderRadius: theme.radius.lg,
    flexDirection: "row",
    gap: theme.spacing.md,
    marginTop: theme.spacing.md,
    padding: theme.spacing.md,
  },
  nudgeIcon: {
    alignItems: "center",
    backgroundColor: "#f5d9bd",
    borderRadius: theme.radius.sm,
    height: 30,
    justifyContent: "center",
    width: 30,
  },
  nudgeText: {
    flex: 1,
    gap: 2,
  },
  nudgeTitle: {
    color: theme.colors.warning,
    fontFamily: theme.fontFamily.extrabold,
    fontSize: 13,
    fontWeight: "800",
  },
  nudgeMessage: {
    color: theme.colors.warning,
    fontFamily: theme.fontFamily.semibold,
    fontSize: theme.typography.caption.fontSize,
    fontWeight: "600",
  },
});
