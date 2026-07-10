// mobile/app/(tabs)/pantry/review.tsx

import { router, useLocalSearchParams } from "expo-router";
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
import { SafeAreaView } from "react-native-safe-area-context";
import { getIngredientById, resolveOrCreateIngredient } from "@/db/ingredients";
import { upsertPantryItem } from "@/db/pantry";
import { checkOffByIngredientIds, completeCheckout } from "@/db/shopping";
import { normalizeSubmittedText, toRequiredSubmittedText } from "@/normalization/text-input";
import { normalizeUnit } from "@/normalization/units";
import { completeOnboarding } from "@/onboarding/storage";
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
  const params = useLocalSearchParams<{ items: string; onboarding?: string; returnTo?: string }>();
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
      if (params.onboarding === "true") {
        await completeOnboarding();
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
      <Text style={styles.heading}>Review Items</Text>
      <Text style={styles.subtitle}>Edit or remove any items before confirming.</Text>
      <FlatList
        data={items}
        keyExtractor={(_, i) => String(i)}
        renderItem={({ item, index }) => (
          <View style={[styles.row, item.confidence < 0.7 && styles.flagged]}>
            {item.confidence < 0.7 && <Text style={styles.flag}>⚠ Check</Text>}
            <TextInput
              style={styles.nameInput}
              value={item.name}
              onChangeText={(v) => updateItem(index, { name: v })}
            />
            <TextInput
              style={styles.qtyInput}
              value={String(item.quantity)}
              onChangeText={(v) => updateItem(index, { quantity: parseFloat(v) || 0 })}
              keyboardType="numeric"
            />
            <Text style={styles.unit}>{item.unit}</Text>
            <Pressable onPress={() => removeItem(index)}>
              <Text style={styles.remove}>✕</Text>
            </Pressable>
          </View>
        )}
      />
      <Pressable
        style={[styles.confirmButton, (saving || acceptedCount === 0) && styles.confirmDisabled]}
        onPress={confirm}
        disabled={saving || acceptedCount === 0}
      >
        {saving ? (
          <ActivityIndicator color={theme.colors.card} />
        ) : (
          <Text style={styles.confirmText}>
            Confirm {acceptedCount} item{acceptedCount !== 1 ? "s" : ""}
          </Text>
        )}
      </Pressable>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.background },
  heading: {
    fontSize: theme.typography.title2.fontSize,
    fontWeight: theme.typography.title2.fontWeight,
    color: theme.colors.text,
    padding: theme.spacing.lg,
  },
  subtitle: {
    fontSize: theme.typography.caption.fontSize,
    color: theme.colors.textSecondary,
    paddingHorizontal: theme.spacing.lg,
    paddingBottom: theme.spacing.sm,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: theme.spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.border,
  },
  flagged: { backgroundColor: theme.colors.warningLight },
  flag: { color: theme.colors.warning, fontSize: 11, marginRight: theme.spacing.xs + 2 },
  nameInput: {
    flex: 1,
    fontSize: 14,
    borderBottomWidth: 1,
    borderColor: theme.colors.border,
    marginRight: theme.spacing.sm,
    color: theme.colors.text,
  },
  qtyInput: {
    width: 60,
    fontSize: 14,
    borderBottomWidth: 1,
    borderColor: theme.colors.border,
    marginRight: theme.spacing.xs,
    textAlign: "right",
    color: theme.colors.text,
  },
  unit: {
    fontSize: theme.typography.caption.fontSize,
    color: theme.colors.textSecondary,
    width: 30,
    marginRight: theme.spacing.sm,
  },
  remove: { color: theme.colors.textDisabled, fontSize: 16 },
  confirmButton: {
    margin: theme.spacing.lg,
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.sm,
    padding: 14,
    alignItems: "center",
    minHeight: 44,
    justifyContent: "center",
  },
  confirmDisabled: { opacity: 0.5 },
  confirmText: {
    color: theme.colors.card,
    fontWeight: theme.typography.headline.fontWeight as "600",
    fontSize: 16,
  },
});
