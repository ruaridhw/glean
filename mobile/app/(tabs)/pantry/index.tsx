// mobile/app/(tabs)/pantry/index.tsx

import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import {
  FlatList,
  LayoutAnimation,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { PantrySkeleton } from "@/components/skeletons/PantrySkeleton";
import { AppScreen } from "@/components/ui/AppScreen";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconButton } from "@/components/ui/IconButton";
import { deletePantryItem, getPantryItems, updatePantryQuantity } from "@/db/pantry";
import {
  formatPantryQuantity,
  getExpiryBadge,
  getPantryCategoryMeta,
  groupPantryItems,
  type PantrySection,
} from "@/pantry/presentation";
import { hapticImpact } from "@/platform/haptics";
import { theme } from "@/theme";
import type { PantryItem } from "@/types";

function expiryToneToBadgeTone(
  tone: "expired" | "soon" | "later",
): "danger" | "warning" | "neutral" {
  if (tone === "expired") return "danger";
  if (tone === "soon") return "warning";
  return "neutral";
}

interface PantryItemCardProps {
  item: PantryItem;
  editingId: number | null;
  editQty: string;
  onStartEdit: (item: PantryItem) => void;
  onChangeEditQty: (quantity: string) => void;
  onCommitEdit: (item: PantryItem) => void;
  onDelete: (item: PantryItem) => void;
}

function PantryItemCard({
  item,
  editingId,
  editQty,
  onStartEdit,
  onChangeEditQty,
  onCommitEdit,
  onDelete,
}: PantryItemCardProps) {
  const meta = getPantryCategoryMeta(item.food_group);
  const expiryBadge = getExpiryBadge(item.expiry_date);
  const isEditing = editingId === item.id;

  return (
    <Card style={styles.itemCard} testID={`pantry.item.${item.id}`}>
      <View style={[styles.categoryDot, { backgroundColor: meta.color }]} />
      <View style={styles.itemContent}>
        <Text style={styles.itemName}>{item.canonical_name}</Text>
        {isEditing ? (
          <TextInput
            style={styles.editInput}
            value={editQty}
            onChangeText={onChangeEditQty}
            keyboardType="numeric"
            onBlur={() => onCommitEdit(item)}
            autoFocus
          />
        ) : (
          <Pressable onPress={() => onStartEdit(item)} accessibilityRole="button">
            <Text style={styles.itemQuantity}>{formatPantryQuantity(item)}</Text>
          </Pressable>
        )}
      </View>
      {expiryBadge ? (
        <Badge label={expiryBadge.label} tone={expiryToneToBadgeTone(expiryBadge.tone)} />
      ) : null}
      <IconButton
        icon="trash-outline"
        accessibilityLabel={`Remove ${item.canonical_name}`}
        color={theme.colors.textSecondary}
        backgroundColor="transparent"
        size={18}
        onPress={() => onDelete(item)}
      />
    </Card>
  );
}

interface PantrySectionViewProps {
  section: PantrySection;
  editingId: number | null;
  editQty: string;
  onStartEdit: (item: PantryItem) => void;
  onChangeEditQty: (quantity: string) => void;
  onCommitEdit: (item: PantryItem) => void;
  onDelete: (item: PantryItem) => void;
}

function PantrySectionView({
  section,
  editingId,
  editQty,
  onStartEdit,
  onChangeEditQty,
  onCommitEdit,
  onDelete,
}: PantrySectionViewProps) {
  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Ionicons
          name={section.meta.icon as keyof typeof Ionicons.glyphMap}
          size={16}
          color={section.meta.color}
        />
        <Text style={styles.groupHeader}>{section.title}</Text>
      </View>
      {section.items.map((item) => (
        <PantryItemCard
          key={item.id}
          item={item}
          editingId={editingId}
          editQty={editQty}
          onStartEdit={onStartEdit}
          onChangeEditQty={onChangeEditQty}
          onCommitEdit={onCommitEdit}
          onDelete={onDelete}
        />
      ))}
    </View>
  );
}

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

  async function deleteItem(item: PantryItem) {
    await hapticImpact("medium");
    await deletePantryItem(item.id);
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    await load();
  }

  const sections = groupPantryItems(items);

  if (loading) {
    return (
      <AppScreen title="Pantry" testID="pantry.screen">
        <PantrySkeleton />
      </AppScreen>
    );
  }

  if (items.length === 0) {
    return (
      <AppScreen
        title="Pantry"
        subtitle="Reduce waste, eat what you have"
        testID="pantry.screen"
        actions={
          <IconButton
            icon="add"
            accessibilityLabel="Add pantry item"
            color={theme.colors.primaryForeground}
            backgroundColor={theme.colors.primary}
            onPress={() => router.push("/(tabs)/pantry/add")}
          />
        }
      >
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
      </AppScreen>
    );
  }

  return (
    <AppScreen
      title="Pantry"
      subtitle={`${items.length} ${items.length === 1 ? "item" : "items"}`}
      testID="pantry.screen"
      actions={
        <IconButton
          icon="add"
          accessibilityLabel="Add pantry item"
          color={theme.colors.primaryForeground}
          backgroundColor={theme.colors.primary}
          onPress={() => router.push("/(tabs)/pantry/add")}
        />
      }
    >
      <FlatList
        testID="pantry.list"
        data={sections}
        keyExtractor={(section) => section.key}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.listContent}
        renderItem={({ item }) => (
          <PantrySectionView
            section={item}
            editingId={editingId}
            editQty={editQty}
            onStartEdit={(pantryItem) => {
              setEditingId(pantryItem.id);
              setEditQty(String(pantryItem.quantity));
            }}
            onChangeEditQty={setEditQty}
            onCommitEdit={commitEdit}
            onDelete={deleteItem}
          />
        )}
      />
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  listContent: { paddingBottom: theme.spacing.xl },
  section: { marginBottom: theme.spacing.lg },
  sectionHeader: {
    alignItems: "center",
    flexDirection: "row",
    gap: theme.spacing.xs,
    marginBottom: theme.spacing.sm,
  },
  groupHeader: {
    ...theme.typography.sectionLabel,
    color: theme.colors.textSecondary,
  },
  itemCard: {
    alignItems: "center",
    flexDirection: "row",
    gap: theme.spacing.md,
    marginBottom: theme.spacing.sm,
    paddingVertical: theme.spacing.md,
  },
  categoryDot: {
    borderRadius: 5,
    height: 10,
    width: 10,
  },
  itemContent: { flex: 1 },
  itemName: {
    color: theme.colors.text,
    fontSize: theme.typography.headline.fontSize,
    fontWeight: theme.typography.headline.fontWeight,
    marginBottom: 2,
  },
  itemQuantity: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.subhead.fontSize,
  },
  editInput: {
    alignSelf: "flex-start",
    borderColor: theme.colors.primary,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    color: theme.colors.text,
    fontSize: theme.typography.subhead.fontSize,
    minWidth: 72,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: theme.spacing.xs,
  },
});
