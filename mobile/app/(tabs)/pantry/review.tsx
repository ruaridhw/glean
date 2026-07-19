// mobile/app/(tabs)/pantry/review.tsx

import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, FlatList, Pressable, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { AppText } from "@/components/ui/AppText";
import { AppTextInput } from "@/components/ui/AppTextInput";
import { Badge } from "@/components/ui/Badge";
import { addPantryItem } from "@/db/pantry";
import { checkOffByIngredientIds, completeCheckout } from "@/db/shopping";
import { isLowConfidence } from "@/intake/presentation";
import { deserializeReviewItems } from "@/intake/serialization";
import type { ReviewItem } from "@/intake/types";
import { useReviewList } from "@/intake/useReviewList";
import { normalizeSubmittedText, toRequiredSubmittedText } from "@/normalization/text-input";
import { theme } from "@/theme";
import { showSuccess } from "@/utils/toast";

type PantryReviewItem = ReviewItem & { unit_price: number | null };

export default function ReviewScreen() {
  const params = useLocalSearchParams<{ items: string; returnTo?: string }>();
  const { items, updateItem, removeItem, acceptedItems, acceptedCount } =
    useReviewList<PantryReviewItem>(() => deserializeReviewItems<PantryReviewItem>(params.items));
  const [saving, setSaving] = useState(false);

  async function confirm() {
    setSaving(true);
    try {
      const resolvedIds: number[] = [];
      for (const item of acceptedItems) {
        const name = toRequiredSubmittedText(item.name) as string;
        const unit = normalizeSubmittedText(item.unit) || "units";
        const { ingredientId } = await addPantryItem({
          name,
          quantity: item.quantity,
          unit,
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
        keyExtractor={(item) => item.review_id}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        renderItem={({ item, index }) => {
          const flagged = isLowConfidence(item);
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
