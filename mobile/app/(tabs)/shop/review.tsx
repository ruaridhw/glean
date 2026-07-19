import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, View } from "react-native";
import { AppScreen } from "@/components/ui/AppScreen";
import { AppText } from "@/components/ui/AppText";
import { AppTextInput } from "@/components/ui/AppTextInput";
import { Card } from "@/components/ui/Card";
import { IconButton } from "@/components/ui/IconButton";
import { isLowConfidence } from "@/intake/presentation";
import { deserializeReviewItems } from "@/intake/serialization";
import { useReviewList } from "@/intake/useReviewList";
import { toRequiredSubmittedText } from "@/normalization/text-input";
import { commitShoppingIntake, type ShopReviewItem } from "@/shop/intake";
import { theme } from "@/theme";
import { showSuccess } from "@/utils/toast";

function parseQuestions(raw: string | undefined): string[] {
  if (!raw) return [];
  return JSON.parse(raw) as string[];
}

export default function ShoppingReviewScreen() {
  const params = useLocalSearchParams<{ items?: string; clarifyingQuestions?: string }>();
  const { items, updateItem, removeItem, acceptedItems, acceptedCount } =
    useReviewList<ShopReviewItem>(() => deserializeReviewItems<ShopReviewItem>(params.items));
  const [saving, setSaving] = useState(false);
  const questions = parseQuestions(params.clarifyingQuestions);

  async function confirm() {
    setSaving(true);
    try {
      const savedCount = await commitShoppingIntake(acceptedItems);
      showSuccess(`Added ${savedCount} item${savedCount !== 1 ? "s" : ""}`);
      router.replace("/(tabs)/shop");
    } catch {
      Alert.alert("Error", "Failed to save shopping items. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppScreen
      title="Review list"
      subtitle="Edit or remove any items before adding them."
      testID="shopping.review.screen"
      scroll
      keyboardAvoiding
    >
      {questions.length > 0 ? (
        <Card style={styles.questionsCard}>
          {questions.map((question) => (
            <AppText key={question} style={styles.questionText}>
              {question}
            </AppText>
          ))}
        </Card>
      ) : null}

      <View style={styles.rows}>
        {items.map((item, index) => (
          <Card key={item.review_id} style={styles.itemCard}>
            <View style={styles.itemHeader}>
              {isLowConfidence(item) ? (
                <View style={styles.flag}>
                  <Ionicons name="warning-outline" size={14} color={theme.colors.warning} />
                  <AppText style={styles.flagText}>Check</AppText>
                </View>
              ) : null}
              <IconButton
                icon="close"
                accessibilityLabel={`Remove ${item.name}`}
                color={theme.colors.textSecondary}
                backgroundColor="transparent"
                size={18}
                onPress={() => removeItem(index)}
              />
            </View>
            <AppTextInput
              style={styles.nameInput}
              value={item.name}
              onChangeText={(value) => updateItem(index, { name: value })}
            />
            <View style={styles.detailRow}>
              <AppTextInput
                style={styles.quantityInput}
                value={String(item.quantity)}
                onChangeText={(value) =>
                  updateItem(index, {
                    quantity: toRequiredSubmittedText(value) ? Number(value) : 1,
                  })
                }
                keyboardType="numeric"
              />
              <AppTextInput
                style={styles.unitInput}
                value={item.unit}
                onChangeText={(value) => updateItem(index, { unit: value })}
              />
            </View>
          </Card>
        ))}
      </View>

      <Pressable
        style={[styles.confirmButton, (saving || acceptedCount === 0) && styles.confirmDisabled]}
        onPress={() => void confirm()}
        disabled={saving || acceptedCount === 0}
      >
        {saving ? (
          <ActivityIndicator color={theme.colors.primaryForeground} />
        ) : (
          <AppText style={styles.confirmText}>
            Add {acceptedCount} item{acceptedCount !== 1 ? "s" : ""}
          </AppText>
        )}
      </Pressable>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  questionsCard: {
    backgroundColor: theme.colors.primaryLight,
    marginBottom: theme.spacing.md,
  },
  questionText: {
    color: theme.colors.text,
    fontSize: theme.typography.caption.fontSize,
  },
  rows: {
    gap: theme.spacing.sm,
  },
  itemCard: {
    gap: theme.spacing.sm,
  },
  itemHeader: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  flag: {
    alignItems: "center",
    flexDirection: "row",
    gap: theme.spacing.xs,
  },
  flagText: {
    color: theme.colors.warning,
    fontSize: theme.typography.caption.fontSize,
    fontWeight: "700",
  },
  nameInput: {
    borderBottomColor: theme.colors.border,
    borderBottomWidth: 1,
    color: theme.colors.text,
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "600",
    paddingVertical: theme.spacing.xs,
  },
  detailRow: {
    flexDirection: "row",
    gap: theme.spacing.sm,
  },
  quantityInput: {
    backgroundColor: theme.colors.muted,
    borderRadius: theme.radius.sm,
    color: theme.colors.text,
    padding: theme.spacing.sm,
    textAlign: "right",
    width: 80,
  },
  unitInput: {
    backgroundColor: theme.colors.muted,
    borderRadius: theme.radius.sm,
    color: theme.colors.text,
    flex: 1,
    padding: theme.spacing.sm,
  },
  confirmButton: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.md,
    justifyContent: "center",
    marginTop: theme.spacing.lg,
    minHeight: 48,
    padding: theme.spacing.md,
  },
  confirmDisabled: { opacity: 0.5 },
  confirmText: {
    color: theme.colors.primaryForeground,
    fontWeight: "700",
  },
});
