import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { getSavedRecipes } from "@/db/recipes";
import { theme } from "@/theme";
import type { Recipe } from "@/types";

export default function MealsScreen() {
  const [tab, setTab] = useState<"saved" | "search">("saved");
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [loading, setLoading] = useState(true);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      void getSavedRecipes().then((r) => {
        setRecipes(r);
        setLoading(false);
      });
    }, []),
  );

  return (
    <SafeAreaView style={s.container} edges={["top"]}>
      <Text style={s.heading}>Meals</Text>
      <View style={s.tabs}>
        {(["saved", "search"] as const).map((t) => (
          <Pressable key={t} style={[s.tab, tab === t && s.tabActive]} onPress={() => setTab(t)}>
            <Text style={tab === t ? s.tabTextActive : s.tabText}>
              {t === "saved" ? "My Recipes" : "Discover"}
            </Text>
          </Pressable>
        ))}
      </View>

      {tab === "saved" ? (
        loading ? (
          <ActivityIndicator style={{ flex: 1 }} color={theme.colors.primary} />
        ) : (
          <FlatList
            data={recipes}
            keyExtractor={(r) => String(r.id)}
            renderItem={({ item }) => (
              <Pressable style={s.row} onPress={() => router.push(`/(tabs)/meals/${item.id}`)}>
                <View style={{ flex: 1 }}>
                  <Text style={s.rowTitle}>{item.title}</Text>
                  <Text style={s.rowMeta}>
                    {[
                      item.cuisine,
                      item.difficulty,
                      item.total_time_mins ? `${item.total_time_mins}min` : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </Text>
                </View>
                <Text style={s.chevron}>›</Text>
              </Pressable>
            )}
            ListEmptyComponent={
              <Text style={s.empty}>No recipes yet. Discover some or import via URL.</Text>
            }
          />
        )
      ) : (
        <>
          <Pressable style={s.discoverBtn} onPress={() => router.push("/(tabs)/meals/search")}>
            <Text style={s.discoverText}>Search recipes →</Text>
          </Pressable>
          <Pressable style={s.importBtn} onPress={() => router.push("/(tabs)/meals/import")}>
            <Text style={s.importText}>Import from URL</Text>
          </Pressable>
        </>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.background },
  heading: {
    fontSize: theme.typography.title2.fontSize,
    fontWeight: theme.typography.title2.fontWeight,
    color: theme.colors.text,
    padding: theme.spacing.lg,
  },
  tabs: {
    flexDirection: "row",
    paddingHorizontal: theme.spacing.lg,
    marginBottom: theme.spacing.sm,
    gap: theme.spacing.sm,
  },
  tab: {
    flex: 1,
    paddingVertical: theme.spacing.sm,
    borderRadius: theme.radius.sm,
    backgroundColor: theme.colors.surface,
    alignItems: "center",
  },
  tabActive: { backgroundColor: theme.colors.primary },
  tabText: { color: theme.colors.textSecondary, fontWeight: "600" },
  tabTextActive: { color: theme.colors.card, fontWeight: "600" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    padding: theme.spacing.lg,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.border,
  },
  rowTitle: {
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "600",
    marginBottom: 2,
    color: theme.colors.text,
  },
  rowMeta: { fontSize: theme.typography.caption.fontSize, color: theme.colors.textSecondary },
  chevron: { fontSize: 20, color: theme.colors.textDisabled },
  empty: {
    textAlign: "center",
    color: theme.colors.textSecondary,
    marginTop: 40,
    fontSize: theme.typography.subhead.fontSize,
  },
  discoverBtn: {
    margin: theme.spacing.lg,
    padding: theme.spacing.md,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colors.primary,
    alignItems: "center",
  },
  discoverText: { color: theme.colors.primary, fontWeight: "600" },
  importBtn: {
    marginHorizontal: theme.spacing.lg,
    marginBottom: theme.spacing.lg,
    padding: theme.spacing.md,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surface,
    alignItems: "center",
  },
  importText: { color: theme.colors.text, fontWeight: "600" },
});
