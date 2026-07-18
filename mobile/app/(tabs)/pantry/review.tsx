// mobile/app/(tabs)/pantry/review.tsx

import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, FlatList, Pressable, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { AppText } from "@/components/ui/AppText";
import { AppTextInput } from "@/components/ui/AppTextInput";
import { Badge } from "@/components/ui/Badge";
import { getIngredientById, resolveOrCreateIngredient } from "@/db/ingredients";
import { upsertPantryItem } from "@/db/pantry";
import { checkOffByIngredientIds, completeCheckout } from "@/db/shopping";
import { normalizeSubmittedText, toRequiredSubmittedText } from "@/normalization/text-input";
import { normalizeUnit } from "@/normalization/units";
import { theme } from "@/theme";
import { showSuccess } from "@/utils/toast";

interface ReviewItem {
  name: string;
  quantity: number;
  unit: string;
  unit_price: number | null;
  confidence: number;
}

export default function ReviewScreen() {
  const params = useLocalSearchParams<{ items: string; returnTo?: string }>();
  const [items, setItems] = useState<ReviewItem[]>(JSON.parse(params.items ?? "[]"));
  const [saving, setSaving] = useState(false);

  function updateItem(index: number, patch: Partial<ReviewItem>) {
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  function removeItem(index: number) {
    setItems((prev) => prev.filter((_, i) => i !== index));
  }

  async function confirm() {
    setSaving(true);
    try {
      const resolvedIds: number[] = [];
      const acceptedItems = items.filter((item) => toRequiredSubmittedText(item.name));
      for (const item of acceptedItems) {
        const name = toRequiredSubmittedText(item.name) as string;
        const unit = normalizeSubmittedText(item.unit) || "units";
        const ingredientId = await resolveOrCreateIngredient({ canonical_name: name });
        const ingredient = await getIngredientById(ingredientId);
        const normalized = normalizeUnit({
          quantity: item.quantity,
          unit,
          canonicalUnit: ingredient?.canonical_unit ?? null,
          canonicalName: name,
        });
        await upsertPantryItem({
          ingredient_id: ingredientId,
          quantity: normalized?.quantity ?? item.quantity,
          unit: normalized?.unit ?? unit,
          unit_price: item.unit_price ?? null,
        });
        resolvedIds.push(ingredientId);
      }
      await checkOffByIngredientIds(resolvedIds);
      if (params.returnTo === "shop") {
        await completeCheckout();
      }
      showSuccess(
        `Added ${acceptedItems.length} item${acceptedItems.length !== 1 ? "s" : ""} to pantry`,
      );
      router.replace(params.returnTo === "shop" ? "/(tabs)/shop" : "/(tabs)/pantry");
    } catch {
      Alert.alert("Error", "Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  const acceptedCount = items.filter((item) => toRequiredSubmittedText(item.name)).length;

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <View style={styles.header}>
        <AppText style={styles.heading}>Review items</AppText>
        <AppText style={styles.subtitle}>
          Edit or remove anything before it goes in the pantry.
        </AppText>
      </View>
      <FlatList
        data={items}
        keyExtractor={(_, i) => String(i)}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        renderItem={({ item, index }) => {
          const flagged = item.confidence < 0.7;
          return (
            <View style={[styles.row, flagged && styles.rowFlagged]}>
              {flagged ? (
                <Badge
                  label="CHECK"
                  backgroundColor={theme.colors.accent}
                  color={theme.colors.primaryForeground}
                />
              ) : null}
              <AppTextInput
                style={styles.nameInput}
                value={item.name}
                onChangeText={(v) => updateItem(index, { name: v })}
              />
              <AppTextInput
                style={styles.qtyInput}
                value={String(item.quantity)}
                onChangeText={(v) => updateItem(index, { quantity: parseFloat(v) || 0 })}
                keyboardType="numeric"
              />
              <AppText style={styles.unit}>{item.unit}</AppText>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`Remove ${item.name}`}
                hitSlop={8}
                onPress={() => removeItem(index)}
              >
                <Ionicons name="close" size={18} color={theme.colors.textDisabled} />
              </Pressable>
            </View>
          );
        }}
      />
      <Pressable
        style={[styles.confirmButton, (saving || acceptedCount === 0) && styles.confirmDisabled]}
        onPress={confirm}
        disabled={saving || acceptedCount === 0}
      >
        {saving ? (
          <ActivityIndicator color={theme.colors.primaryForeground} />
        ) : (
          <AppText style={styles.confirmText}>
            Confirm {acceptedCount} item{acceptedCount !== 1 ? "s" : ""}
          </AppText>
        )}
      </Pressable>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.background },
  header: {
    paddingHorizontal: theme.spacing.lg,
    paddingTop: theme.spacing.lg,
    paddingBottom: theme.spacing.xs,
  },
  heading: {
    fontSize: 24,
    fontFamily: theme.fontFamily.extrabold,
    fontWeight: "800",
    letterSpacing: -0.5,
    color: theme.colors.text,
  },
  subtitle: {
    fontSize: 13,
    fontFamily: theme.fontFamily.semibold,
    fontWeight: "600",
    color: theme.colors.textSecondary,
    marginTop: 4,
  },
  listContent: {
    paddingHorizontal: theme.spacing.lg,
    paddingTop: theme.spacing.md,
    gap: 10,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.md,
    backgroundColor: theme.colors.card,
    borderRadius: theme.radius.lg,
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: 14,
    ...theme.shadow.card,
  },
  rowFlagged: { backgroundColor: theme.colors.warningLight },
  nameInput: {
    flex: 1,
    fontSize: 15,
    fontFamily: theme.fontFamily.bold,
    fontWeight: "700",
    borderBottomWidth: 1.5,
    borderColor: theme.colors.border,
    paddingBottom: 3,
    color: theme.colors.text,
  },
  qtyInput: {
    width: 56,
    fontSize: 14,
    fontFamily: theme.fontFamily.bold,
    fontWeight: "700",
    borderBottomWidth: 1.5,
    borderColor: theme.colors.border,
    paddingBottom: 3,
    textAlign: "right",
    color: theme.colors.text,
  },
  unit: {
    width: 30,
    fontSize: 12,
    fontFamily: theme.fontFamily.semibold,
    fontWeight: "600",
    color: theme.colors.textSecondary,
  },
  confirmButton: {
    margin: theme.spacing.lg,
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.pill,
    padding: 15,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 44,
    ...theme.shadow.fab,
  },
  confirmDisabled: { opacity: 0.5 },
  confirmText: {
    color: theme.colors.primaryForeground,
    fontFamily: theme.fontFamily.extrabold,
    fontWeight: "800",
    fontSize: 15,
  },
});
