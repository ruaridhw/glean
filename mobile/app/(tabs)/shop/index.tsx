// mobile/app/(tabs)/shop/index.tsx

import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { showSuccess } from "@/utils/toast";
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
import {
  addManualShoppingItem,
  completeCheckout,
  deleteShoppingItem,
  getShoppingListItems,
  toggleShoppingItem,
} from "@/db/shopping";
import { theme } from "@/theme";
import type { ShoppingListItem } from "@/types";

export default function ShopScreen() {
  const [items, setItems] = useState<ShoppingListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [newItemName, setNewItemName] = useState("");
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setItems(await getShoppingListItems());
    setLoading(false);
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  async function handleAdd() {
    if (!newItemName.trim()) return;
    setAdding(true);
    await addManualShoppingItem({ name: newItemName.trim() });
    setNewItemName("");
    setAdding(false);
    await load();
  }

  async function handleToggle(item: ShoppingListItem) {
    await toggleShoppingItem(item.id, !item.is_checked);
    await load();
  }

  async function handleDelete(item: ShoppingListItem) {
    await deleteShoppingItem(item.id);
    await load();
  }

  function handleCompleteCheckout() {
    const checkedCount = items.filter((i) => i.is_checked).length;
    const uncheckedCount = items.filter((i) => !i.is_checked).length;

    Alert.alert(
      "Completed checkout",
      "Did you get a receipt? Scanning it will update your pantry automatically.",
      [
        {
          text: "Scan receipt",
          onPress: () => {
            router.push("/(tabs)/pantry/scan?returnTo=shop");
          },
        },
        {
          text: "Skip — just clear checked",
          onPress: () => {
            Alert.alert(
              "Clear checked items?",
              `${checkedCount} checked item${checkedCount !== 1 ? "s" : ""} will be removed.${
                uncheckedCount > 0
                  ? `\n\n${uncheckedCount} unchecked item${uncheckedCount !== 1 ? "s" : ""} will remain for next time.`
                  : ""
              }`,
              [
                { text: "Cancel", style: "cancel" },
                {
                  text: "Clear",
                  onPress: async () => {
                    await completeCheckout();
                    showSuccess("Checkout complete");
                    await load();
                  },
                },
              ],
            );
          },
        },
        { text: "Cancel", style: "cancel" },
      ],
    );
  }

  const unchecked = items.filter((i) => !i.is_checked);
  const checked = items.filter((i) => i.is_checked);

  if (loading) return <ActivityIndicator style={{ flex: 1 }} />;

  return (
    <SafeAreaView style={s.container} edges={["top"]}>
      <View style={s.header}>
        <Text style={s.heading}>Shopping List</Text>
        {checked.length > 0 && (
          <Pressable style={s.checkoutBtn} onPress={handleCompleteCheckout}>
            <Text style={s.checkoutBtnText}>Completed checkout</Text>
          </Pressable>
        )}
      </View>

      <FlatList
        data={[...unchecked, ...checked]}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <View style={[s.itemRow, item.is_checked && s.checkedRow]}>
            <Pressable style={s.checkbox} onPress={() => handleToggle(item)}>
              <Text style={s.checkboxText}>{item.is_checked ? "☑" : "☐"}</Text>
            </Pressable>
            <View style={{ flex: 1 }}>
              <Text style={[s.itemName, item.is_checked && s.checkedText]}>{item.name}</Text>
              {item.quantity != null && (
                <Text style={s.itemQty}>
                  {item.quantity}
                  {item.unit}
                </Text>
              )}
            </View>
            <View style={s.sourceTag}>
              <Text style={s.sourceTagText}>{item.source}</Text>
            </View>
            <Pressable onPress={() => handleDelete(item)}>
              <Text style={s.deleteText}>✕</Text>
            </Pressable>
          </View>
        )}
        ListFooterComponent={
          <View style={s.addRow}>
            <TextInput
              style={s.addInput}
              value={newItemName}
              onChangeText={setNewItemName}
              placeholder="Add item…"
              placeholderTextColor={theme.colors.textDisabled}
              returnKeyType="done"
              onSubmitEditing={handleAdd}
            />
            <Pressable
              style={[s.addBtn, (!newItemName.trim() || adding) && s.addBtnDisabled]}
              onPress={handleAdd}
              disabled={adding || !newItemName.trim()}
            >
              <Text style={s.addBtnText}>Add</Text>
            </Pressable>
          </View>
        }
        ListEmptyComponent={<Text style={s.empty}>Your shopping list is empty.</Text>}
      />
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.background },
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
  checkoutBtn: {
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.sm,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
  },
  checkoutBtnText: { color: theme.colors.card, fontWeight: "600", fontSize: 13 },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    padding: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.border,
    gap: 10,
  },
  checkedRow: { opacity: 0.5 },
  checkbox: { width: 24 },
  checkboxText: { fontSize: 20, color: theme.colors.text },
  itemName: { fontSize: theme.typography.subhead.fontSize, color: theme.colors.text },
  checkedText: { textDecorationLine: "line-through" },
  itemQty: {
    fontSize: theme.typography.caption.fontSize,
    color: theme.colors.textSecondary,
    marginTop: 1,
  },
  sourceTag: {
    backgroundColor: theme.colors.surface,
    borderRadius: theme.radius.sm,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  sourceTagText: { fontSize: 10, color: theme.colors.textSecondary },
  deleteText: { color: theme.colors.textDisabled, fontSize: 16 },
  addRow: {
    flexDirection: "row",
    gap: theme.spacing.sm,
    padding: theme.spacing.lg,
    borderTopWidth: 1,
    borderColor: theme.colors.border,
  },
  addInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.sm,
    padding: 10,
    fontSize: theme.typography.subhead.fontSize,
    color: theme.colors.text,
  },
  addBtn: {
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.sm,
    paddingHorizontal: theme.spacing.lg,
    justifyContent: "center",
  },
  addBtnDisabled: { opacity: 0.5 },
  addBtnText: { color: theme.colors.card, fontWeight: "600" },
  empty: {
    textAlign: "center",
    color: theme.colors.textSecondary,
    marginTop: 40,
    fontSize: 14,
  },
});
