import { router, useFocusEffect } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import { KeyboardAvoidingView, Platform, StyleSheet, View } from "react-native";
import { ShoppingSkeleton } from "@/components/skeletons/ShoppingSkeleton";
import { AppScreen, type AppScreenChip } from "@/components/ui/AppScreen";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconButton } from "@/components/ui/IconButton";
import {
  addManualShoppingItem,
  deleteShoppingItem,
  getShoppingListItems,
  toggleShoppingItem,
} from "@/db/shopping";
import { toRequiredSubmittedText } from "@/normalization/text-input";
import { hapticImpact } from "@/platform/haptics";
import { groupShoppingItems } from "@/shop/presentation";
import { CheckoutBar, ShoppingAddControls, ShoppingList } from "@/shop/shopping-list-components";
import { theme } from "@/theme";
import type { ShoppingListItem } from "@/types";

export default function ShopScreen() {
  const [items, setItems] = useState<ShoppingListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [newItemName, setNewItemName] = useState("");
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const result = await getShoppingListItems();
    setItems(result);
    setLoading(false);
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const handleAdd = useCallback(async () => {
    const name = toRequiredSubmittedText(newItemName);
    if (!name) return;
    setAdding(true);
    await addManualShoppingItem({ name });
    setNewItemName("");
    setAdding(false);
    await load();
  }, [load, newItemName]);

  const handleToggle = useCallback(
    async (item: ShoppingListItem) => {
      await hapticImpact("light");
      await toggleShoppingItem(item.id, !item.is_checked);
      await load();
    },
    [load],
  );

  const handleDelete = useCallback(
    async (item: ShoppingListItem) => {
      await deleteShoppingItem(item.id);
      await load();
    },
    [load],
  );

  const unchecked = items.filter((item) => !item.is_checked);
  const checked = items.filter((item) => item.is_checked);
  const sections = groupShoppingItems(items);
  const canAddItem = Boolean(toRequiredSubmittedText(newItemName));

  const chips: AppScreenChip[] = [
    { label: `${unchecked.length} to buy`, tone: "primary" },
    { label: `${checked.length} checked`, tone: "neutral" },
  ];

  const addControls = useMemo(
    () => (
      <ShoppingAddControls
        adding={adding}
        canAddItem={canAddItem}
        newItemName={newItemName}
        onAdd={() => void handleAdd()}
        onChangeNewItemName={setNewItemName}
      />
    ),
    [adding, canAddItem, handleAdd, newItemName],
  );

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      style={styles.keyboardView}
    >
      <AppScreen
        title="Shopping"
        chips={chips}
        testID="shop.screen"
        actions={
          <IconButton
            icon="sparkles-outline"
            accessibilityLabel="Describe list"
            backgroundColor={theme.colors.surface}
            color={theme.colors.primaryDark}
            size={20}
            style={styles.describeAction}
            onPress={() => router.push("/(tabs)/shop/describe" as never)}
          />
        }
      >
        {loading ? (
          <ShoppingSkeleton />
        ) : (
          <View style={styles.screenContent}>
            {items.length === 0 ? (
              <>
                {addControls}
                <EmptyState
                  testID="shop.emptyState"
                  icon="cart-outline"
                  title="Your shopping list is empty"
                  message="Plan some meals and we'll figure out what you need."
                  actions={[
                    {
                      label: "Go to meal plan",
                      onPress: () => router.push("/(tabs)/plan" as never),
                    },
                  ]}
                />
              </>
            ) : (
              <ShoppingList
                sections={sections}
                addControls={addControls}
                onToggle={(shoppingItem) => void handleToggle(shoppingItem)}
                onDelete={(shoppingItem) => void handleDelete(shoppingItem)}
              />
            )}
            <CheckoutBar
              checkedCount={checked.length}
              onScanReceipt={() => router.push("/(tabs)/pantry/scan?returnTo=shop")}
            />
          </View>
        )}
      </AppScreen>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  keyboardView: { flex: 1, backgroundColor: theme.colors.background },
  screenContent: {
    flex: 1,
  },
  describeAction: {
    height: 44,
    width: 44,
    ...theme.shadow.card,
  },
});
