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
import { SwipeDeleteRow } from "@/components/swipe-delete-row";
import { AppScreen, type AppScreenChip } from "@/components/ui/AppScreen";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconButton } from "@/components/ui/IconButton";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { deletePantryItem, getPantryItems, updatePantryQuantity } from "@/db/pantry";
import { toRequiredSubmittedText } from "@/normalization/text-input";
import {
  formatPantryQuantity,
  getExpiryBadge,
  groupPantryItems,
  isExpiringSoon,
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

/** Items whose expiry badge is near-term (expired or within a couple of days). */
function countExpiring(items: PantryItem[]): number {
  return items.filter((item) => isExpiringSoon(item)).length;
}

const ALL_FILTER = "all";

interface PantryFilter {
  key: string;
  label: string;
}

function ScanButton() {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Scan receipt"
      style={styles.scanButton}
      onPress={() => {
        void hapticImpact("light");
        router.push("/(tabs)/pantry/scan");
      }}
    >
      <Ionicons name="camera-outline" size={18} color={theme.colors.primaryForeground} />
      <Text style={styles.scanButtonText}>Scan</Text>
    </Pressable>
  );
}

interface FilterChipRowProps {
  filters: PantryFilter[];
  active: string;
  onSelect: (key: string) => void;
}

function FilterChipRow({ filters, active, onSelect }: FilterChipRowProps) {
  return (
    <View style={styles.filterRow}>
      {filters.map((filter) => {
        const selected = filter.key === active;
        return (
          <Pressable
            key={filter.key}
            accessibilityRole="button"
            accessibilityState={{ selected }}
            onPress={() => onSelect(filter.key)}
            style={[
              styles.filterChip,
              selected ? styles.filterChipSelected : styles.filterChipIdle,
            ]}
          >
            <Text
              style={[
                styles.filterChipLabel,
                { color: selected ? theme.colors.primaryForeground : theme.colors.text },
              ]}
            >
              {filter.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
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
  const expiryBadge = getExpiryBadge(item.expiry_date);
  const isEditing = editingId === item.id;

  return (
    <SwipeDeleteRow
      actionTestID={`pantry-row-delete-action-${item.id}`}
      iconTestID={`pantry-row-delete-icon-${item.id}`}
      rowTestID={`pantry-row-${item.id}`}
      onDelete={() => onDelete(item)}
    >
      {(deleteActive) => (
        <Card style={styles.itemCard} testID={`pantry.item.${item.id}`}>
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
            color={deleteActive ? theme.colors.danger : theme.colors.textDisabled}
            backgroundColor={deleteActive ? theme.colors.dangerLight : "transparent"}
            size={18}
            onPress={() => onDelete(item)}
          />
        </Card>
      )}
    </SwipeDeleteRow>
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
      <SectionHeader
        title={section.title}
        icon={section.meta.icon as keyof typeof Ionicons.glyphMap}
        iconColor={section.meta.fg}
        iconBackground={section.meta.bg}
        count={section.items.length}
      />
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
  const [filter, setFilter] = useState<string>(ALL_FILTER);

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
    const normalizedQty = toRequiredSubmittedText(editQty);
    const qty = normalizedQty ? parseFloat(normalizedQty) : Number.NaN;
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

  const allSections = groupPantryItems(items);

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
        actions={<ScanButton />}
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

  const expiringCount = countExpiring(items);
  const chips: AppScreenChip[] = [
    { label: `${items.length} ${items.length === 1 ? "item" : "items"}`, tone: "primary" },
  ];
  if (expiringCount > 0) {
    chips.push({ label: `${expiringCount} expiring`, tone: "warning" });
  }

  const filters: PantryFilter[] = [
    { key: ALL_FILTER, label: `All · ${items.length}` },
    ...allSections.map((section) => ({
      key: section.key,
      label: `${section.meta.shortLabel} ${section.items.length}`,
    })),
  ];

  const visibleSections =
    filter === ALL_FILTER ? allSections : allSections.filter((section) => section.key === filter);

  return (
    <AppScreen title="Pantry" chips={chips} testID="pantry.screen" actions={<ScanButton />}>
      <FilterChipRow filters={filters} active={filter} onSelect={setFilter} />
      <FlatList
        testID="pantry.list"
        data={visibleSections}
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
  scanButton: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.pill,
    flexDirection: "row",
    gap: 6,
    height: 44,
    paddingHorizontal: theme.spacing.lg,
    ...theme.shadow.fab,
  },
  scanButtonText: {
    color: theme.colors.primaryForeground,
    fontSize: 13,
    fontFamily: theme.fontFamily.extrabold,
    fontWeight: "800",
  },
  filterRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.sm,
    paddingBottom: theme.spacing.md,
  },
  filterChip: {
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  filterChipSelected: {
    backgroundColor: theme.colors.ink,
    borderColor: theme.colors.ink,
  },
  filterChipIdle: {
    backgroundColor: theme.colors.card,
    borderColor: theme.colors.border,
  },
  filterChipLabel: {
    fontSize: 13,
    fontFamily: theme.fontFamily.extrabold,
    fontWeight: "800",
  },
  listContent: { paddingBottom: theme.spacing.xl },
  section: { marginBottom: theme.spacing.lg },
  itemCard: {
    alignItems: "center",
    flexDirection: "row",
    gap: theme.spacing.md,
    marginBottom: theme.spacing.sm,
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: 14,
  },
  itemContent: { flex: 1 },
  itemName: {
    color: theme.colors.text,
    fontSize: 16,
    fontFamily: theme.fontFamily.bold,
    fontWeight: "700",
    marginBottom: 2,
  },
  itemQuantity: {
    color: theme.colors.mutedForeground,
    fontSize: 14,
    fontFamily: theme.fontFamily.semibold,
    fontWeight: "600",
  },
  editInput: {
    alignSelf: "flex-start",
    borderColor: theme.colors.primary,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    color: theme.colors.text,
    fontFamily: theme.fontFamily.semibold,
    fontSize: 14,
    minWidth: 72,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: theme.spacing.xs,
  },
});
