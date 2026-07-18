import { Ionicons } from "@expo/vector-icons";
import type { ReactElement } from "react";
import { Pressable, SectionList, StyleSheet, View } from "react-native";
import { SwipeDeleteRow } from "@/components/swipe-delete-row";
import { AppText } from "@/components/ui/AppText";
import { AppTextInput } from "@/components/ui/AppTextInput";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import {
  formatShoppingItemLabel,
  getShoppingSourceLabel,
  getShoppingSourceTone,
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
}

export function ShoppingAddControls({
  adding,
  canAddItem,
  newItemName,
  onAdd,
  onChangeNewItemName,
}: ShoppingAddControlsProps) {
  return (
    <View style={styles.addRow}>
      <AppTextInput
        style={styles.addInput}
        value={newItemName}
        onChangeText={onChangeNewItemName}
        placeholder="Add item…"
        returnKeyType="done"
        onSubmitEditing={onAdd}
      />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Add item"
        testID="shop.addButton"
        style={[styles.addButton, (!canAddItem || adding) && styles.addButtonDisabled]}
        onPress={onAdd}
        disabled={adding || !canAddItem}
      >
        <Ionicons name="add" size={24} color={theme.colors.primaryForeground} />
      </Pressable>
    </View>
  );
}

interface CheckoutBarProps {
  checkedCount: number;
  onScanReceipt: () => void;
}

export function CheckoutBar({ checkedCount, onScanReceipt }: CheckoutBarProps) {
  if (checkedCount === 0) return null;

  return (
    <View testID="shop.pinnedCheckoutActions" style={styles.checkoutBar}>
      <View style={styles.checkoutText}>
        <AppText style={styles.checkoutTitle}>
          {checkedCount} item{checkedCount === 1 ? "" : "s"} in cart
        </AppText>
        <AppText style={styles.checkoutSubtitle}>Scan the receipt to restock your pantry</AppText>
      </View>
      <Pressable accessibilityRole="button" style={styles.scanPill} onPress={onScanReceipt}>
        <AppText style={styles.scanPillText}>Scan receipt</AppText>
      </Pressable>
    </View>
  );
}

interface ShoppingListProps {
  addControls: ReactElement;
  onDelete: (item: ShoppingListItem) => void;
  onToggle: (item: ShoppingListItem) => void;
  sections: ShoppingSection[];
}

export function ShoppingList({ addControls, onDelete, onToggle, sections }: ShoppingListProps) {
  return (
    <SectionList<ShoppingListItem, ShoppingSection>
      testID="shop.shoppingList"
      style={styles.shoppingList}
      sections={sections}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => <ShoppingRow item={item} onToggle={onToggle} onDelete={onDelete} />}
      renderSectionHeader={({ section }) => <SectionHeader title={section.title} />}
      ListHeaderComponent={addControls}
      contentContainerStyle={styles.listContent}
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
      {() => (
        <Card style={[styles.itemCard, checked && styles.checkedItemCard]}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`${checked ? "Uncheck" : "Check"} ${item.name}`}
            style={styles.itemMain}
            onPress={() => onToggle(item)}
          >
            <View style={[styles.check, checked && styles.checkChecked]}>
              {checked ? (
                <Ionicons name="checkmark" size={14} color={theme.colors.primaryForeground} />
              ) : null}
            </View>
            <AppText style={[styles.itemLabel, checked && styles.checkedText]} numberOfLines={2}>
              {formatShoppingItemLabel(item)}
            </AppText>
          </Pressable>
          {checked ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Remove ${item.name}`}
              hitSlop={8}
              onPress={() => onDelete(item)}
            >
              <Ionicons name="close" size={18} color={theme.colors.textDisabled} />
            </Pressable>
          ) : (
            <Badge
              label={getShoppingSourceLabel(item.source)}
              tone={getShoppingSourceTone(item.source)}
            />
          )}
        </Card>
      )}
    </SwipeDeleteRow>
  );
}

const styles = StyleSheet.create({
  addRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: theme.spacing.sm,
    marginBottom: theme.spacing.xs,
  },
  addInput: {
    backgroundColor: theme.colors.surface,
    borderRadius: theme.radius.pill,
    color: theme.colors.text,
    flex: 1,
    fontFamily: theme.fontFamily.semibold,
    fontSize: 14,
    paddingHorizontal: 18,
    paddingVertical: 13,
    ...theme.shadow.card,
  },
  addButton: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.pill,
    height: 46,
    justifyContent: "center",
    width: 46,
  },
  addButtonDisabled: { opacity: 0.5 },
  checkoutBar: {
    alignItems: "center",
    backgroundColor: theme.colors.ink,
    borderRadius: theme.radius.xl,
    flexDirection: "row",
    gap: theme.spacing.md,
    marginTop: theme.spacing.md,
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: 14,
  },
  checkoutText: { flex: 1 },
  checkoutTitle: {
    color: theme.colors.primaryForeground,
    fontFamily: theme.fontFamily.extrabold,
    fontSize: 14,
  },
  checkoutSubtitle: {
    color: "rgba(255,255,255,0.6)",
    fontFamily: theme.fontFamily.semibold,
    fontSize: 12,
    marginTop: 2,
  },
  scanPill: {
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.pill,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  scanPillText: {
    color: theme.colors.primaryForeground,
    fontFamily: theme.fontFamily.extrabold,
    fontSize: 12,
  },
  shoppingList: {
    flex: 1,
  },
  listContent: {
    gap: 10,
    paddingBottom: theme.spacing.md,
  },
  itemCard: {
    alignItems: "center",
    flexDirection: "row",
    gap: 14,
  },
  checkedItemCard: {
    opacity: 0.6,
  },
  itemMain: {
    alignItems: "center",
    flex: 1,
    flexDirection: "row",
    gap: 14,
  },
  check: {
    alignItems: "center",
    borderColor: theme.colors.borderStrong,
    borderRadius: 12,
    borderWidth: 2,
    height: 24,
    justifyContent: "center",
    width: 24,
  },
  checkChecked: {
    backgroundColor: theme.colors.primary,
    borderColor: theme.colors.primary,
  },
  itemLabel: {
    color: theme.colors.text,
    flex: 1,
    fontFamily: theme.fontFamily.bold,
    fontSize: 15,
  },
  checkedText: {
    textDecorationLine: "line-through",
  },
});
