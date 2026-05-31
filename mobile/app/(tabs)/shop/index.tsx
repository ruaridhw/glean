// mobile/app/(tabs)/shop/index.tsx

import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import {
  KeyboardAvoidingView,
  PanResponder,
  Platform,
  Pressable,
  SectionList,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { ShoppingSkeleton } from "@/components/skeletons/ShoppingSkeleton";
import { AppScreen } from "@/components/ui/AppScreen";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconButton } from "@/components/ui/IconButton";
import { SectionHeader } from "@/components/ui/SectionHeader";
import {
  addManualShoppingItem,
  completeCheckout,
  deleteShoppingItem,
  getShoppingListItems,
  toggleShoppingItem,
} from "@/db/shopping";
import { toRequiredSubmittedText } from "@/normalization/text-input";
import { hapticImpact } from "@/platform/haptics";
import {
  formatShoppingQuantity,
  getShoppingSourceLabel,
  groupShoppingItems,
  type ShoppingSection,
} from "@/shop/presentation";
import { theme } from "@/theme";
import type { ShoppingListItem } from "@/types";
import { showSuccess } from "@/utils/toast";

function ShoppingRow({
  item,
  onToggle,
  onDelete,
}: {
  item: ShoppingListItem;
  onToggle: (item: ShoppingListItem) => void;
  onDelete: (item: ShoppingListItem) => void;
}) {
  const checked = item.is_checked;
  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_, gestureState) =>
          Math.abs(gestureState.dx) > 16 && Math.abs(gestureState.dx) > Math.abs(gestureState.dy),
        onPanResponderRelease: (_, gestureState) => {
          if (gestureState.dx < -48 && Math.abs(gestureState.dx) > Math.abs(gestureState.dy)) {
            onDelete(item);
          }
        },
        onPanResponderTerminationRequest: () => true,
      }),
    [item, onDelete],
  );

  return (
    <Card
      testID={`shopping-row-${item.name}`}
      style={[styles.itemCard, checked && styles.checkedItemCard]}
      {...panResponder.panHandlers}
    >
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${checked ? "Uncheck" : "Check"} ${item.name}`}
        style={styles.itemPressable}
        onPress={() => onToggle(item)}
      >
        <View style={[styles.checkbox, checked && styles.checkboxChecked]}>
          {checked ? (
            <Ionicons name="checkmark" size={14} color={theme.colors.primaryForeground} />
          ) : null}
        </View>
        <View style={styles.itemContent}>
          <Text style={[styles.itemName, checked && styles.checkedText]}>{item.name}</Text>
          <View style={styles.itemMetaRow}>
            <Text style={styles.itemQuantity}>{formatShoppingQuantity(item)}</Text>
            <Badge label={getShoppingSourceLabel(item.source)} />
          </View>
        </View>
      </Pressable>
      <IconButton
        icon="trash-outline"
        accessibilityLabel={`Remove ${item.name}`}
        color={theme.colors.textSecondary}
        backgroundColor="transparent"
        size={18}
        onPress={() => onDelete(item)}
      />
    </Card>
  );
}

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

  async function handleAdd() {
    const name = toRequiredSubmittedText(newItemName);
    if (!name) return;
    setAdding(true);
    await addManualShoppingItem({ name });
    setNewItemName("");
    setAdding(false);
    await load();
  }

  async function handleToggle(item: ShoppingListItem) {
    await hapticImpact("light");
    await toggleShoppingItem(item.id, !item.is_checked);
    await load();
  }

  async function handleDelete(item: ShoppingListItem) {
    await deleteShoppingItem(item.id);
    await load();
  }

  async function handleClearChecked() {
    await completeCheckout();
    showSuccess("Checkout complete");
    await load();
  }

  const unchecked = items.filter((item) => !item.is_checked);
  const checked = items.filter((item) => item.is_checked);
  const sections = groupShoppingItems(items);
  const canAddItem = Boolean(toRequiredSubmittedText(newItemName));

  const renderAddControls = () => (
    <Card style={styles.addCard}>
      <TextInput
        style={styles.addInput}
        value={newItemName}
        onChangeText={setNewItemName}
        placeholder="Add item..."
        placeholderTextColor={theme.colors.textDisabled}
        returnKeyType="done"
        onSubmitEditing={handleAdd}
      />
      <Pressable
        style={[styles.addButton, (!canAddItem || adding) && styles.addButtonDisabled]}
        onPress={handleAdd}
        disabled={adding || !canAddItem}
      >
        <Text style={styles.addButtonText}>Add</Text>
      </Pressable>
      <Pressable
        style={styles.describeButton}
        onPress={() => router.push("/(tabs)/shop/describe" as never)}
      >
        <Ionicons name="sparkles-outline" size={16} color={theme.colors.primary} />
        <Text style={styles.describeButtonText}>Describe</Text>
      </Pressable>
    </Card>
  );

  const checkoutActions =
    checked.length > 0 ? (
      <Card testID="shop.pinnedCheckoutActions" style={styles.checkoutCard}>
        <View style={styles.checkoutHeader}>
          <View style={styles.checkoutTitleRow}>
            <Ionicons name="checkmark-done-outline" size={18} color={theme.colors.primary} />
            <Text style={styles.checkoutTitle}>Completed checkout</Text>
          </View>
          <Badge label={`${checked.length} checked`} tone="primary" />
        </View>
        <View style={styles.checkoutActions}>
          <Pressable
            style={styles.primaryAction}
            onPress={() => router.push("/(tabs)/pantry/scan?returnTo=shop")}
          >
            <Text style={styles.primaryActionText}>Scan receipt</Text>
          </Pressable>
          <Pressable style={styles.secondaryAction} onPress={() => void handleClearChecked()}>
            <Text style={styles.secondaryActionText}>Clear checked</Text>
          </Pressable>
        </View>
      </Card>
    ) : null;

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      style={styles.keyboardView}
    >
      <AppScreen
        title="Shopping"
        subtitle={`${unchecked.length} remaining · ${checked.length} checked`}
        testID="shop.screen"
      >
        {loading ? (
          <ShoppingSkeleton />
        ) : (
          <View style={styles.screenContent}>
            {items.length === 0 ? (
              <>
                {renderAddControls()}
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
              <SectionList<ShoppingListItem, ShoppingSection>
                sections={sections}
                keyExtractor={(item) => String(item.id)}
                renderItem={({ item }) => (
                  <ShoppingRow
                    item={item}
                    onToggle={(shoppingItem) => void handleToggle(shoppingItem)}
                    onDelete={(shoppingItem) => void handleDelete(shoppingItem)}
                  />
                )}
                renderSectionHeader={({ section }) => (
                  <View style={styles.sectionHeader}>
                    <SectionHeader title={section.title} />
                  </View>
                )}
                ListHeaderComponent={renderAddControls}
                contentContainerStyle={[
                  styles.listContent,
                  checkoutActions ? styles.listContentWithCheckout : null,
                ]}
                keyboardShouldPersistTaps="handled"
                showsVerticalScrollIndicator={false}
                stickySectionHeadersEnabled={false}
              />
            )}
            {checkoutActions}
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
  checkoutCard: {
    gap: theme.spacing.sm,
  },
  checkoutHeader: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  checkoutTitle: {
    color: theme.colors.text,
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "700",
  },
  checkoutTitleRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: theme.spacing.xs,
  },
  checkoutActions: {
    flexDirection: "row",
    gap: theme.spacing.sm,
  },
  primaryAction: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.md,
    flex: 1,
    padding: theme.spacing.md,
  },
  primaryActionText: {
    color: theme.colors.primaryForeground,
    fontWeight: "700",
  },
  secondaryAction: {
    alignItems: "center",
    backgroundColor: theme.colors.muted,
    borderRadius: theme.radius.md,
    flex: 1,
    padding: theme.spacing.md,
  },
  secondaryActionText: {
    color: theme.colors.text,
    fontWeight: "700",
  },
  addCard: {
    flexDirection: "row",
    gap: theme.spacing.sm,
    marginBottom: theme.spacing.md,
  },
  addInput: {
    backgroundColor: theme.colors.muted,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    color: theme.colors.text,
    flex: 1,
    fontSize: theme.typography.subhead.fontSize,
    padding: theme.spacing.md,
  },
  addButton: {
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.md,
    justifyContent: "center",
    paddingHorizontal: theme.spacing.lg,
  },
  addButtonDisabled: { opacity: 0.5 },
  addButtonText: {
    color: theme.colors.primaryForeground,
    fontWeight: "700",
  },
  describeButton: {
    alignItems: "center",
    borderColor: theme.colors.primary,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    flexDirection: "row",
    gap: theme.spacing.xs,
    justifyContent: "center",
    paddingHorizontal: theme.spacing.md,
  },
  describeButtonText: {
    color: theme.colors.primary,
    fontWeight: "700",
  },
  listContent: {
    gap: theme.spacing.sm,
    paddingBottom: theme.spacing.md,
  },
  listContentWithCheckout: {
    paddingBottom: theme.spacing.xl,
  },
  sectionHeader: {
    marginTop: theme.spacing.xs,
  },
  itemCard: {
    alignItems: "center",
    flexDirection: "row",
    gap: theme.spacing.md,
  },
  itemPressable: {
    alignItems: "center",
    flex: 1,
    flexDirection: "row",
    gap: theme.spacing.md,
  },
  checkedItemCard: {
    opacity: 0.65,
  },
  checkbox: {
    alignItems: "center",
    borderColor: theme.colors.border,
    borderRadius: 11,
    borderWidth: 2,
    height: 22,
    justifyContent: "center",
    width: 22,
  },
  checkboxChecked: {
    backgroundColor: theme.colors.primary,
    borderColor: theme.colors.primary,
  },
  itemContent: {
    flex: 1,
    gap: theme.spacing.xs,
  },
  itemName: {
    color: theme.colors.text,
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "600",
  },
  checkedText: {
    textDecorationLine: "line-through",
  },
  itemMetaRow: {
    alignItems: "center",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.sm,
  },
  itemQuantity: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.caption.fontSize,
  },
});
