import { Ionicons } from "@expo/vector-icons";
import type { ReactElement } from "react";
import { Pressable, SectionList, StyleSheet, Text, TextInput, View } from "react-native";
import { SwipeDeleteRow } from "@/components/swipe-delete-row";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import {
  formatShoppingQuantity,
  getShoppingSourceLabel,
  type ShoppingSection,
} from "@/shop/presentation";
import { theme } from "@/theme";
import type { ShoppingListItem } from "@/types";

interface ShoppingAddControlsProps {
  adding: boolean;
  canAddItem: boolean;
  newItemName: string;
  onAdd: () => void;
  onChangeNewItemName: (value: string) => void;
  onDescribe: () => void;
}

export function ShoppingAddControls({
  adding,
  canAddItem,
  newItemName,
  onAdd,
  onChangeNewItemName,
  onDescribe,
}: ShoppingAddControlsProps) {
  return (
    <Card style={styles.addCard}>
      <TextInput
        style={styles.addInput}
        value={newItemName}
        onChangeText={onChangeNewItemName}
        placeholder="Add item..."
        placeholderTextColor={theme.colors.textDisabled}
        returnKeyType="done"
        onSubmitEditing={onAdd}
      />
      <Pressable
        style={[styles.addButton, (!canAddItem || adding) && styles.addButtonDisabled]}
        onPress={onAdd}
        disabled={adding || !canAddItem}
      >
        <Text style={styles.addButtonText}>Add</Text>
      </Pressable>
      <Pressable style={styles.describeButton} onPress={onDescribe}>
        <Ionicons name="sparkles-outline" size={16} color={theme.colors.primary} />
        <Text style={styles.describeButtonText}>Describe</Text>
      </Pressable>
    </Card>
  );
}

interface CheckoutActionsProps {
  checkedCount: number;
  onClearChecked: () => void;
  onScanReceipt: () => void;
}

export function CheckoutActions({
  checkedCount,
  onClearChecked,
  onScanReceipt,
}: CheckoutActionsProps) {
  if (checkedCount === 0) return null;

  return (
    <Card testID="shop.pinnedCheckoutActions" style={styles.checkoutCard}>
      <View style={styles.checkoutHeader}>
        <View style={styles.checkoutTitleRow}>
          <Ionicons name="checkmark-done-outline" size={18} color={theme.colors.primary} />
          <Text style={styles.checkoutTitle}>Completed checkout</Text>
        </View>
        <Badge label={`${checkedCount} checked`} tone="primary" />
      </View>
      <View style={styles.checkoutActions}>
        <Pressable style={styles.primaryAction} onPress={onScanReceipt}>
          <Text style={styles.primaryActionText}>Scan receipt</Text>
        </Pressable>
        <Pressable style={styles.secondaryAction} onPress={onClearChecked}>
          <Text style={styles.secondaryActionText}>Clear checked</Text>
        </Pressable>
      </View>
    </Card>
  );
}

interface ShoppingListProps {
  addControls: ReactElement;
  hasCheckoutActions: boolean;
  onDelete: (item: ShoppingListItem) => void;
  onToggle: (item: ShoppingListItem) => void;
  sections: ShoppingSection[];
}

export function ShoppingList({
  addControls,
  hasCheckoutActions,
  onDelete,
  onToggle,
  sections,
}: ShoppingListProps) {
  return (
    <SectionList<ShoppingListItem, ShoppingSection>
      testID="shop.shoppingList"
      style={styles.shoppingList}
      sections={sections}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => <ShoppingRow item={item} onToggle={onToggle} onDelete={onDelete} />}
      renderSectionHeader={({ section }) => (
        <View style={styles.sectionHeader}>
          <SectionHeader title={section.title} />
        </View>
      )}
      ListHeaderComponent={addControls}
      contentContainerStyle={[
        styles.listContent,
        hasCheckoutActions ? styles.listContentWithCheckout : null,
      ]}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
      stickySectionHeadersEnabled={false}
    />
  );
}

interface ShoppingRowProps {
  item: ShoppingListItem;
  onToggle: (item: ShoppingListItem) => void;
  onDelete: (item: ShoppingListItem) => void;
}

function ShoppingRow({ item, onToggle, onDelete }: ShoppingRowProps) {
  const checked = item.is_checked;

  return (
    <SwipeDeleteRow
      actionTestID={`shopping-row-delete-action-${item.id}`}
      iconTestID={`shopping-row-delete-icon-${item.id}`}
      rowTestID={`shopping-row-${item.id}`}
      onDelete={() => onDelete(item)}
    >
      {(deleteActive) => (
        <Card style={[styles.itemCard, checked && styles.checkedItemCard]}>
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
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Remove ${item.name}`}
            hitSlop={8}
            style={[styles.deleteButton, deleteActive && styles.deleteButtonActive]}
            onPress={() => onDelete(item)}
          >
            <Ionicons
              name="trash-outline"
              size={18}
              color={deleteActive ? theme.colors.danger : theme.colors.textSecondary}
            />
          </Pressable>
        </Card>
      )}
    </SwipeDeleteRow>
  );
}

const styles = StyleSheet.create({
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
  shoppingList: {
    flex: 1,
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
  deleteButton: {
    alignItems: "center",
    borderRadius: theme.radius.pill,
    height: 40,
    justifyContent: "center",
    width: 40,
  },
  deleteButtonActive: {
    backgroundColor: "#FEE2E2",
  },
});
