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
import { getIngredientById, resolveOrCreateIngredient } from "@/db/ingredients";
import { upsertPantryItem } from "@/db/pantry";
import { checkOffByIngredientIds, completeCheckout } from "@/db/shopping";
import { normalizeUnit } from "@/normalization/units";

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
      for (const item of items) {
        const ingredientId = await resolveOrCreateIngredient({ canonical_name: item.name });
        const ingredient = await getIngredientById(ingredientId);
        const normalized = normalizeUnit({
          quantity: item.quantity,
          unit: item.unit,
          canonicalUnit: ingredient?.canonical_unit ?? null,
          canonicalName: item.name,
        });
        await upsertPantryItem({
          ingredient_id: ingredientId,
          quantity: normalized?.quantity ?? item.quantity,
          unit: normalized?.unit ?? item.unit,
          unit_price: item.unit_price ?? null,
        });
        resolvedIds.push(ingredientId);
      }
      await checkOffByIngredientIds(resolvedIds);
      if (params.returnTo === "shop") {
        await completeCheckout();
      }
      router.replace(params.returnTo === "shop" ? "/(tabs)/shop" : "/(tabs)/pantry");
    } catch {
      Alert.alert("Error", "Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <View style={styles.container}>
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
      <Pressable style={styles.confirmButton} onPress={confirm} disabled={saving}>
        {saving ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.confirmText}>
            Confirm {items.length} item{items.length !== 1 ? "s" : ""}
          </Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  heading: { fontSize: 22, fontWeight: "700", padding: 16 },
  subtitle: { fontSize: 13, color: "#888", paddingHorizontal: 16, paddingBottom: 8 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: "#eee",
  },
  flagged: { backgroundColor: "#fff8f0" },
  flag: { color: "#f7a04a", fontSize: 11, marginRight: 6 },
  nameInput: { flex: 1, fontSize: 14, borderBottomWidth: 1, borderColor: "#ddd", marginRight: 8 },
  qtyInput: {
    width: 60,
    fontSize: 14,
    borderBottomWidth: 1,
    borderColor: "#ddd",
    marginRight: 4,
    textAlign: "right",
  },
  unit: { fontSize: 12, color: "#888", width: 30, marginRight: 8 },
  remove: { color: "#ccc", fontSize: 16 },
  confirmButton: {
    margin: 16,
    backgroundColor: "#2a9d8f",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
  },
  confirmText: { color: "#fff", fontWeight: "600", fontSize: 16 },
});
