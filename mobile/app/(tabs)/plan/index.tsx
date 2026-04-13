// mobile/app/(tabs)/plan/index.tsx

import { router, useFocusEffect, useLocalSearchParams } from "expo-router";
import { useCallback, useState } from "react";
import { Alert, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useSuggestMeals } from "@/api/hooks";
import { PlanSkeleton } from "@/components/skeletons/PlanSkeleton";
import { EmptyState } from "@/components/ui/EmptyState";
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
import { compressPantry } from "@/suggestions/compress";
import { theme } from "@/theme";
import type { MealPlanEntry } from "@/types";
import { showError, showSuccess } from "@/utils/toast";

export default function PlanScreen() {
  const [entries, setEntries] = useState<MealPlanEntry[]>([]);
  const [mealsPerWeek, setMealsPerWeek] = useState(5);
  const [loading, setLoading] = useState(true);
  const suggestMutation = useSuggestMeals();
  const params = useLocalSearchParams<{ add_recipe_id?: string }>();

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
      load();
      if (params.add_recipe_id) {
        handleAddRecipe(Number(params.add_recipe_id));
      }
      return () => {
        suggestMutation.reset();
      };
    }, [load, params.add_recipe_id, handleAddRecipe, suggestMutation]),
  );

  async function handleMarkCooked(entry: MealPlanEntry) {
    Alert.alert(
      "Mark as cooked?",
      `This will decrement pantry quantities for "${entry.recipe_title}".`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Mark Cooked",
          onPress: async () => {
            await markMealAsCooked(entry.id);
            await load();
          },
        },
      ],
    );
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
    const recipeHistory = recipes.map((r) => ({
      recipe_id: r.id,
      title: r.title,
      last_cooked_at: r.last_cooked_at ?? null,
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

  const emptySlots = Math.max(0, mealsPerWeek - entries.length);

  if (loading) return <PlanSkeleton rows={mealsPerWeek} />;

  if (entries.length === 0) {
    return (
      <SafeAreaView style={s.container} edges={["top"]}>
        <View style={s.header}>
          <Text style={s.heading}>This Week</Text>
        </View>
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
      </SafeAreaView>
    );
  }

  type ListItem = MealPlanEntry | { id: number; isEmpty: true };

  return (
    <SafeAreaView style={s.container} edges={["top"]}>
      <View style={s.header}>
        <Text style={s.heading}>This Week</Text>
      </View>

      <FlatList<ListItem>
        data={[
          ...entries,
          ...Array.from(
            { length: emptySlots },
            (_, i): ListItem => ({ id: -(i + 1), isEmpty: true }),
          ),
        ]}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => {
          if ("isEmpty" in item) {
            return (
              <Pressable
                style={s.emptySlot}
                onPress={() => router.push("/(tabs)/meals/search" as never)}
              >
                <Text style={s.emptySlotText}>+ Add a meal</Text>
              </Pressable>
            );
          }
          const entry = item as MealPlanEntry;
          return (
            <View style={[s.entryRow, entry.cooked_at != null && s.cookedRow]}>
              <View style={{ flex: 1 }}>
                <Text style={[s.entryTitle, entry.cooked_at != null && s.cookedTitle]}>
                  {entry.recipe_title}
                </Text>
                {entry.cooked_at != null && <Text style={s.cookedLabel}>Cooked ✓</Text>}
              </View>
              {entry.cooked_at == null && (
                <Pressable style={s.cookBtn} onPress={() => handleMarkCooked(entry)}>
                  <Text style={s.cookBtnText}>Cooked</Text>
                </Pressable>
              )}
              <Pressable onPress={() => handleDelete(entry)} style={s.deleteBtn}>
                <Text style={s.deleteBtnText}>✕</Text>
              </Pressable>
            </View>
          );
        }}
      />
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: theme.spacing.lg,
  },
  heading: {
    fontSize: theme.typography.title2.fontSize,
    fontWeight: theme.typography.title2.fontWeight,
    color: theme.colors.text,
  },
  entryRow: {
    flexDirection: "row",
    alignItems: "center",
    padding: theme.spacing.lg,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.border,
  },
  cookedRow: {
    opacity: 0.6,
  },
  entryTitle: {
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: theme.typography.headline.fontWeight,
    color: theme.colors.text,
  },
  cookedTitle: {
    textDecorationLine: "line-through",
  },
  cookedLabel: {
    fontSize: theme.typography.caption.fontSize,
    color: theme.colors.primary,
    marginTop: theme.spacing.xs,
  },
  cookBtn: {
    borderWidth: 1,
    borderColor: theme.colors.primary,
    borderRadius: theme.radius.sm,
    paddingHorizontal: theme.spacing.sm + 2,
    paddingVertical: theme.spacing.xs,
    marginRight: theme.spacing.sm,
  },
  cookBtnText: {
    color: theme.colors.primary,
    fontSize: theme.typography.caption.fontSize,
  },
  deleteBtn: {
    padding: theme.spacing.xs,
  },
  deleteBtnText: {
    color: theme.colors.textDisabled,
    fontSize: theme.typography.body.fontSize,
  },
  emptySlot: {
    padding: theme.spacing.lg,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.border,
    borderStyle: "dashed",
  },
  emptySlotText: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.subhead.fontSize,
  },
});
