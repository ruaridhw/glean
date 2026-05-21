import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import type { ShoppingProposalItem } from "@/api/types";
import { AppScreen } from "@/components/ui/AppScreen";
import { Card } from "@/components/ui/Card";
import { IconButton } from "@/components/ui/IconButton";
import { addAiShoppingItems } from "@/db/shopping";
import { theme } from "@/theme";
import { showSuccess } from "@/utils/toast";

type ReviewItem = Pick<
  ShoppingProposalItem,
  "name" | "quantity" | "unit" | "api_ingredient_id" | "category" | "confidence"
> & { review_id: string };

function parseItems(raw: string | undefined): ReviewItem[] {
  if (!raw) return [];
  const seen = new Map<string, number>();
  return (JSON.parse(raw) as ShoppingProposalItem[]).map((item) => ({
    ...item,
    review_id: (() => {
      const base = `${item.name}:${item.unit}:${item.api_ingredient_id ?? ""}:${item.category ?? ""}`;
      const occurrence = seen.get(base) ?? 0;
      seen.set(base, occurrence + 1);
      return `${base}:${occurrence}`;
    })(),
  }));
}

function parseQuestions(raw: string | undefined): string[] {
  if (!raw) return [];
  return JSON.parse(raw) as string[];
}

export default function ShoppingReviewScreen() {
  const params = useLocalSearchParams<{ items?: string; clarifyingQuestions?: string }>();
  const [items, setItems] = useState<ReviewItem[]>(() => parseItems(params.items));
  const [saving, setSaving] = useState(false);
  const questions = parseQuestions(params.clarifyingQuestions);

  function updateItem(index: number, patch: Partial<ReviewItem>) {
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  function removeItem(index: number) {
    setItems((prev) => prev.filter((_, i) => i !== index));
  }

  async function confirm() {
    setSaving(true);
    try {
      const accepted = items
        .filter((item) => item.name.trim().length > 0)
        .map((item) => ({
          name: item.name.trim(),
          quantity: item.quantity,
          unit: item.unit,
          api_ingredient_id: item.api_ingredient_id,
          category: item.category,
        }));
      await addAiShoppingItems(accepted);
      showSuccess(`Added ${accepted.length} item${accepted.length !== 1 ? "s" : ""}`);
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
            <Text key={question} style={styles.questionText}>
              {question}
            </Text>
          ))}
        </Card>
      ) : null}

      <View style={styles.rows}>
        {items.map((item, index) => (
          <Card key={item.review_id} style={styles.itemCard}>
            <View style={styles.itemHeader}>
              {item.confidence < 0.7 ? (
                <View style={styles.flag}>
                  <Ionicons name="warning-outline" size={14} color={theme.colors.warning} />
                  <Text style={styles.flagText}>Check</Text>
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
            <TextInput
              style={styles.nameInput}
              value={item.name}
              onChangeText={(value) => updateItem(index, { name: value })}
            />
            <View style={styles.detailRow}>
              <TextInput
                style={styles.quantityInput}
                value={String(item.quantity)}
                onChangeText={(value) =>
                  updateItem(index, { quantity: value.trim() ? Number(value) : 1 })
                }
                keyboardType="numeric"
              />
              <TextInput
                style={styles.unitInput}
                value={item.unit}
                onChangeText={(value) => updateItem(index, { unit: value.trim() || "units" })}
              />
            </View>
          </Card>
        ))}
      </View>

      <Pressable
        style={[styles.confirmButton, (saving || items.length === 0) && styles.confirmDisabled]}
        onPress={() => void confirm()}
        disabled={saving || items.length === 0}
      >
        {saving ? (
          <ActivityIndicator color={theme.colors.primaryForeground} />
        ) : (
          <Text style={styles.confirmText}>
            Add {items.length} item{items.length !== 1 ? "s" : ""}
          </Text>
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
