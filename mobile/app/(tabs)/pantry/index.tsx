// mobile/app/(tabs)/pantry/index.tsx

import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import {
  Alert,
  FlatList,
  LayoutAnimation,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { PantrySkeleton } from "@/components/skeletons/PantrySkeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { deletePantryItem, getPantryItems, updatePantryQuantity } from "@/db/pantry";
import { theme } from "@/theme";
import type { PantryItem } from "@/types";

export default function PantryScreen() {
  const [items, setItems] = useState<PantryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editQty, setEditQty] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    const result = await getPantryItems();
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setItems(result);
    setLoading(false);
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  async function commitEdit(item: PantryItem) {
    const qty = parseFloat(editQty);
    if (!Number.isNaN(qty) && qty > 0) {
      await updatePantryQuantity(item.id, qty);
    }
    setEditingId(null);
    await load();
  }

  function confirmDelete(item: PantryItem) {
    Alert.alert("Remove from pantry", `Remove ${item.canonical_name}?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Remove",
        style: "destructive",
        onPress: async () => {
          await deletePantryItem(item.id);
          LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
          await load();
        },
      },
    ]);
  }

  const grouped = items.reduce<Record<string, PantryItem[]>>((acc, item) => {
    const group = item.food_group ?? "other";
    if (!acc[group]) acc[group] = [];
    acc[group].push(item);
    return acc;
  }, {});

  if (loading)
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <Text testID="pantry.heading" style={styles.heading}>
          Pantry
        </Text>
        <PantrySkeleton />
      </SafeAreaView>
    );

  if (items.length === 0) {
    return (
      <SafeAreaView style={styles.container} edges={["top"]}>
        <Text style={styles.heading} testID="pantry.heading">
          Pantry
        </Text>
        <EmptyState
          testID="pantry.emptyState"
          icon="basket-outline"
          title="Your pantry is empty"
          message="Scan a receipt or describe what you have to get started."
          actions={[
            { label: "Scan receipt", onPress: () => router.push("/(tabs)/pantry/scan") },
            { label: "Describe items", onPress: () => router.push("/(tabs)/pantry/describe") },
          ]}
        />
        <Pressable style={styles.fab} testID="pantry.fab" onPress={() => router.push("/(tabs)/pantry/add")}>
          <Text style={styles.fabText}>＋</Text>
        </Pressable>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <Text style={styles.heading} testID="pantry.heading">
        Pantry
      </Text>
      <FlatList
        testID="pantry.list"
        data={Object.entries(grouped)}
        keyExtractor={([group]) => group}
        renderItem={({ item: [group, groupItems] }) => (
          <View>
            <Text style={styles.groupHeader}>{group.toUpperCase()}</Text>
            {groupItems.map((item) => (
              <View key={item.id} style={styles.row}>
                <Text style={styles.name}>{item.canonical_name}</Text>
                {editingId === item.id ? (
                  <TextInput
                    style={styles.editInput}
                    value={editQty}
                    onChangeText={setEditQty}
                    keyboardType="numeric"
                    onBlur={() => commitEdit(item)}
                    autoFocus
                  />
                ) : (
                  <Pressable
                    onPress={() => {
                      setEditingId(item.id);
                      setEditQty(String(item.quantity));
                    }}
                  >
                    <Text style={styles.qty}>
                      {item.quantity}
                      {item.unit}
                    </Text>
                  </Pressable>
                )}
                <Pressable onPress={() => confirmDelete(item)}>
                  <Text style={styles.delete}>✕</Text>
                </Pressable>
              </View>
            ))}
          </View>
        )}
      />
      <Pressable
        style={styles.fab}
        testID="pantry.fab"
        onPress={() => router.push("/(tabs)/pantry/add")}
      >
        <Text style={styles.fabText}>＋</Text>
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
  groupHeader: {
    ...theme.typography.sectionLabel,
    color: theme.colors.textSecondary,
    paddingHorizontal: theme.spacing.lg,
    paddingTop: theme.spacing.md,
    paddingBottom: theme.spacing.xs,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.border,
  },
  name: { flex: 1, fontSize: theme.typography.subhead.fontSize, color: theme.colors.text },
  qty: { fontSize: theme.typography.subhead.fontSize, color: theme.colors.primary, marginRight: theme.spacing.md },
  editInput: {
    width: 80,
    borderWidth: 1,
    borderColor: theme.colors.primary,
    borderRadius: theme.radius.sm,
    padding: theme.spacing.xs,
    fontSize: theme.typography.subhead.fontSize,
    marginRight: theme.spacing.md,
  },
  delete: { color: theme.colors.textDisabled, fontSize: 16 },
  fab: {
    position: "absolute",
    bottom: theme.spacing.xl,
    right: theme.spacing.xl,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: theme.colors.primary,
    justifyContent: "center",
    alignItems: "center",
    ...theme.shadow.fab,
  },
  fabText: { color: theme.colors.card, fontSize: 28, lineHeight: 32 },
});
