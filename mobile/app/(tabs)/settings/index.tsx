// mobile/app/(tabs)/settings/index.tsx

import Slider from "@react-native-community/slider";
import { File, Paths } from "expo-file-system";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { apiClient } from "@/api/client";
import { signOut } from "@/auth/cognito";
import { getUserConfig, saveUserConfig } from "@/db/config";
import { theme } from "@/theme";

const DIETARY_FLAGS = [
  "Vegetarian",
  "Vegan",
  "Gluten-Free",
  "Dairy-Free",
  "Nut-Free",
  "Keto",
  "Paleo",
];

export default function SettingsScreen() {
  const [configId, setConfigId] = useState("");
  const [tolerance, setTolerance] = useState(0.5);
  const [servings, setServings] = useState("2");
  const [mealsPerWeek, setMealsPerWeek] = useState("5");
  const [dietaryFlags, setDietaryFlags] = useState<string[]>([]);
  const [maxTime, setMaxTime] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const config = await getUserConfig();
      setConfigId(config.id);
      setTolerance(config.purchase_tolerance);
      setServings(String(config.preferred_servings));
      setMealsPerWeek(String(config.meals_per_week));
      setDietaryFlags(config.dietary_flags);
      setMaxTime(config.max_active_time_mins ? String(config.max_active_time_mins) : "");
      setLoading(false);
    }
    void load();
  }, []);

  async function save() {
    await saveUserConfig({
      id: configId,
      purchase_tolerance: tolerance,
      preferred_servings: parseInt(servings, 10) || 2,
      meals_per_week: parseInt(mealsPerWeek, 10) || 5,
      dietary_flags: dietaryFlags,
      max_active_time_mins: maxTime ? parseInt(maxTime, 10) : null,
    });
    Alert.alert("Saved");
  }

  function toggleFlag(flag: string) {
    setDietaryFlags((prev) =>
      prev.includes(flag) ? prev.filter((f) => f !== flag) : [...prev, flag],
    );
  }

  async function exportDb() {
    const dbFile = new File(Paths.document, "SQLite", "glean.db");
    if (!dbFile.exists) {
      Alert.alert("No database found");
      return;
    }

    const formData = new FormData();
    formData.append("file", {
      uri: dbFile.uri,
      name: "glean.db",
      type: "application/octet-stream",
    } as unknown as Blob);

    try {
      await apiClient.postForm("/dev/export-db", formData);
      Alert.alert("Exported", "Database uploaded to S3 for debugging.");
    } catch {
      Alert.alert("Export failed", "Could not upload database. Check your connection.");
    }
  }

  function handleSignOut() {
    Alert.alert("Sign out", "You will need to sign in again to use AI features.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Sign out",
        style: "destructive",
        onPress: async () => {
          await signOut();
          router.replace("/sign-in");
        },
      },
    ]);
  }

  if (loading) return null;

  return (
    <ScrollView style={s.container} contentContainerStyle={{ padding: theme.spacing.lg }}>
      <Text style={s.heading}>Settings</Text>

      <Text style={s.sectionHeading}>Purchase Tolerance</Text>
      <Text style={s.description}>
        {tolerance <= 0.2
          ? "Strict: pantry ingredients only"
          : tolerance <= 0.5
            ? "Moderate: minor shopping OK"
            : "Open: happy to buy new ingredients"}
      </Text>
      <Slider
        style={{ height: 40 }}
        minimumValue={0}
        maximumValue={1}
        step={0.1}
        value={tolerance}
        onValueChange={setTolerance}
        minimumTrackTintColor={theme.colors.primary}
        thumbTintColor={theme.colors.primary}
      />

      <Text style={s.sectionHeading}>Meals per Week</Text>
      <TextInput
        style={s.input}
        value={mealsPerWeek}
        onChangeText={setMealsPerWeek}
        keyboardType="number-pad"
      />

      <Text style={s.sectionHeading}>Default Servings</Text>
      <TextInput
        style={s.input}
        value={servings}
        onChangeText={setServings}
        keyboardType="number-pad"
      />

      <Text style={s.sectionHeading}>Max Active Cooking Time (minutes)</Text>
      <TextInput
        style={s.input}
        value={maxTime}
        onChangeText={setMaxTime}
        keyboardType="number-pad"
        placeholder="No limit"
        placeholderTextColor={theme.colors.textDisabled}
      />

      <Text style={s.sectionHeading}>Dietary Preferences</Text>
      <View style={s.flags}>
        {DIETARY_FLAGS.map((flag) => (
          <Pressable
            key={flag}
            style={[s.flagBtn, dietaryFlags.includes(flag) && s.flagBtnActive]}
            onPress={() => toggleFlag(flag)}
          >
            <Text style={dietaryFlags.includes(flag) ? s.flagTextActive : s.flagText}>{flag}</Text>
          </Pressable>
        ))}
      </View>

      <Pressable style={s.saveBtn} onPress={save}>
        <Text style={s.saveBtnText}>Save Settings</Text>
      </Pressable>

      <Text style={s.sectionHeading}>Account</Text>
      <Pressable style={s.dangerBtn} onPress={handleSignOut}>
        <Text style={s.dangerBtnText}>Sign out</Text>
      </Pressable>

      {__DEV__ && (
        <>
          <Text style={s.sectionHeading}>Developer</Text>
          <Pressable style={s.devBtn} onPress={exportDb}>
            <Text style={s.devBtnText}>Export SQLite DB</Text>
          </Pressable>
        </>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.background },
  heading: {
    fontSize: theme.typography.title2.fontSize,
    fontWeight: theme.typography.title2.fontWeight,
    color: theme.colors.text,
    marginBottom: theme.spacing.xl,
  },
  sectionHeading: {
    fontSize: theme.typography.sectionLabel.fontSize,
    fontWeight: theme.typography.sectionLabel.fontWeight,
    textTransform: "uppercase",
    letterSpacing: 0.7,
    color: theme.colors.textSecondary,
    marginTop: theme.spacing.xl,
    marginBottom: theme.spacing.sm,
  },
  description: {
    fontSize: theme.typography.caption.fontSize,
    color: theme.colors.textSecondary,
    marginBottom: theme.spacing.xs,
  },
  input: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.sm,
    padding: 10,
    fontSize: theme.typography.subhead.fontSize,
    color: theme.colors.text,
  },
  flags: { flexDirection: "row", flexWrap: "wrap", gap: theme.spacing.sm },
  flagBtn: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.pill,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: 6,
  },
  flagBtnActive: {
    borderColor: theme.colors.primary,
    backgroundColor: theme.colors.primary,
  },
  flagText: { fontSize: 13, color: theme.colors.text },
  flagTextActive: { fontSize: 13, color: theme.colors.card },
  saveBtn: {
    marginTop: theme.spacing.xl,
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.md,
    padding: 14,
    alignItems: "center",
  },
  saveBtnText: {
    color: theme.colors.card,
    fontWeight: theme.typography.headline.fontWeight,
    fontSize: 16,
  },
  dangerBtn: {
    borderWidth: 1,
    borderColor: theme.colors.warning,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    alignItems: "center",
  },
  dangerBtnText: { color: theme.colors.warning, fontWeight: "600" },
  devBtn: {
    marginTop: theme.spacing.sm,
    borderWidth: 1,
    borderColor: theme.colors.warning,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    alignItems: "center",
  },
  devBtnText: { color: theme.colors.warning },
});
