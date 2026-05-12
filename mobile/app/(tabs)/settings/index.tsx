// mobile/app/(tabs)/settings/index.tsx

import { Ionicons } from "@expo/vector-icons";
import Slider from "@react-native-community/slider";
import { File, Paths } from "expo-file-system";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Alert, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { apiClient } from "@/api/client";
import { signOut } from "@/auth/google";
import { AppScreen } from "@/components/ui/AppScreen";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatsRow } from "@/components/ui/StatsRow";
import { getUserConfig, saveUserConfig } from "@/db/config";
import { hapticImpact } from "@/platform/haptics";
import {
  buildIntegerOptions,
  DIETARY_OPTIONS,
  getToleranceLabel,
  SETTINGS_OPTION_RANGES,
  validateBoundedInteger,
} from "@/settings/presentation";
import { theme } from "@/theme";

const dinnerOptions = buildIntegerOptions(SETTINGS_OPTION_RANGES.dinnersPerWeek);
const servingOptions = buildIntegerOptions(SETTINGS_OPTION_RANGES.defaultServings);

function ChoiceChip({
  label,
  accessibilityLabel,
  selected,
  onPress,
}: {
  label: string;
  accessibilityLabel?: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={{ selected }}
      style={[styles.chip, selected && styles.chipSelected]}
      onPress={onPress}
    >
      {selected ? (
        <Ionicons name="checkmark" size={14} color={theme.colors.primaryForeground} />
      ) : null}
      <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{label}</Text>
    </Pressable>
  );
}

export default function SettingsScreen() {
  const [configId, setConfigId] = useState("");
  const [tolerance, setTolerance] = useState(0.5);
  const [servings, setServings] = useState(2);
  const [mealsPerWeek, setMealsPerWeek] = useState(5);
  const [dietaryFlags, setDietaryFlags] = useState<string[]>([]);
  const [maxTime, setMaxTime] = useState("");
  const [loading, setLoading] = useState(true);
  const [maxTimeError, setMaxTimeError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      const config = await getUserConfig();
      setConfigId(config.id);
      setTolerance(config.purchase_tolerance);
      setServings(config.preferred_servings);
      setMealsPerWeek(config.meals_per_week);
      setDietaryFlags(config.dietary_flags);
      setMaxTime(config.max_active_time_mins ? String(config.max_active_time_mins) : "");
      setLoading(false);
    }
    void load();
  }, []);

  function handleMaxTimeChange(value: string) {
    setMaxTime(value);
    if (!value) {
      setMaxTimeError(null);
      return;
    }
    setMaxTimeError(
      validateBoundedInteger(
        value,
        SETTINGS_OPTION_RANGES.maxActiveTimeMins.min,
        SETTINGS_OPTION_RANGES.maxActiveTimeMins.max,
        "Max active time",
      ),
    );
  }

  function toggleFlag(flag: string) {
    void hapticImpact("light");
    setDietaryFlags((current) =>
      current.includes(flag) ? current.filter((existing) => existing !== flag) : [...current, flag],
    );
  }

  async function save() {
    if (maxTimeError) return;
    await saveUserConfig({
      id: configId,
      purchase_tolerance: tolerance,
      preferred_servings: servings,
      meals_per_week: mealsPerWeek,
      dietary_flags: dietaryFlags,
      max_active_time_mins: maxTime ? parseInt(maxTime, 10) : null,
    });
    Alert.alert("Saved");
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

  async function handleSignOut() {
    await signOut();
    router.replace("/sign-in");
  }

  if (loading) {
    return (
      <AppScreen
        title="Settings"
        subtitle="Loading preferences"
        scroll
        keyboardAvoiding
        testID="settings.screen"
      >
        <Card>
          <Text style={styles.loadingText}>Loading settings...</Text>
        </Card>
      </AppScreen>
    );
  }

  return (
    <AppScreen
      title="Settings"
      subtitle="Preferences and account"
      scroll
      keyboardAvoiding
      testID="settings.screen"
    >
      <StatsRow
        stats={[
          { value: String(mealsPerWeek), label: "Dinners" },
          { value: String(servings), label: "Servings" },
          { value: String(dietaryFlags.length), label: "Diets" },
          { value: `${Math.round(tolerance * 100)}%`, label: "Tolerance" },
        ]}
      />

      <SectionHeader title="Preferences" subtitle="Used for suggestions" />

      <Card style={styles.sectionCard}>
        <Text style={styles.fieldTitle}>Purchase tolerance</Text>
        <Text style={styles.description}>{getToleranceLabel(tolerance)}</Text>
        <Slider
          style={styles.slider}
          minimumValue={0}
          maximumValue={1}
          step={0.1}
          value={tolerance}
          onValueChange={setTolerance}
          minimumTrackTintColor={theme.colors.primary}
          thumbTintColor={theme.colors.primary}
        />
      </Card>

      <Card style={styles.sectionCard}>
        <Text style={styles.fieldTitle}>Dinners per week</Text>
        <View style={styles.chipRow}>
          {dinnerOptions.map((option) => (
            <ChoiceChip
              key={option}
              label={String(option)}
              accessibilityLabel={`${option} dinners per week`}
              selected={mealsPerWeek === option}
              onPress={() => {
                void hapticImpact("light");
                setMealsPerWeek(option);
              }}
            />
          ))}
        </View>
      </Card>

      <Card style={styles.sectionCard}>
        <Text style={styles.fieldTitle}>Default servings</Text>
        <View style={styles.chipRow}>
          {servingOptions.map((option) => (
            <ChoiceChip
              key={option}
              label={`${option} servings`}
              accessibilityLabel={`${option} default servings`}
              selected={servings === option}
              onPress={() => {
                void hapticImpact("light");
                setServings(option);
              }}
            />
          ))}
        </View>
      </Card>

      <Card style={styles.sectionCard}>
        <Text style={styles.fieldTitle}>Max active cooking time</Text>
        <TextInput
          style={[styles.input, maxTimeError ? styles.inputError : null]}
          value={maxTime}
          onChangeText={handleMaxTimeChange}
          keyboardType="number-pad"
          placeholder="No limit"
          placeholderTextColor={theme.colors.textDisabled}
        />
        {maxTimeError ? <Text style={styles.errorText}>{maxTimeError}</Text> : null}
      </Card>

      <SectionHeader title="Dietary preferences" />
      <Card style={styles.sectionCard}>
        <View style={styles.chipRow}>
          {DIETARY_OPTIONS.map((flag) => (
            <ChoiceChip
              key={flag}
              label={flag}
              selected={dietaryFlags.includes(flag)}
              onPress={() => toggleFlag(flag)}
            />
          ))}
        </View>
      </Card>

      <Pressable
        accessibilityRole="button"
        style={[styles.saveButton, maxTimeError && styles.saveButtonDisabled]}
        onPress={save}
        disabled={Boolean(maxTimeError)}
      >
        <Text style={styles.saveButtonText}>Save Settings</Text>
      </Pressable>

      <SectionHeader title="Account" />
      <Card style={styles.sectionCard}>
        <Pressable style={styles.rowAction} onPress={() => void handleSignOut()}>
          <Ionicons name="log-out-outline" size={18} color={theme.colors.danger} />
          <Text style={styles.dangerText}>Sign out</Text>
        </Pressable>
      </Card>

      {__DEV__ ? (
        <>
          <SectionHeader title="Developer" />
          <Card style={styles.sectionCard}>
            <Pressable style={styles.rowAction} onPress={() => void exportDb()}>
              <Ionicons name="cloud-upload-outline" size={18} color={theme.colors.warning} />
              <Text style={styles.warningText}>Export SQLite DB</Text>
            </Pressable>
          </Card>
        </>
      ) : null}
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  loadingText: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.subhead.fontSize,
  },
  sectionCard: {
    gap: theme.spacing.md,
    marginBottom: theme.spacing.md,
  },
  fieldTitle: {
    color: theme.colors.text,
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "700",
  },
  description: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.caption.fontSize,
    lineHeight: 18,
  },
  slider: {
    height: 40,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: theme.spacing.sm,
  },
  chip: {
    alignItems: "center",
    backgroundColor: theme.colors.muted,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    flexDirection: "row",
    gap: theme.spacing.xs,
    minHeight: 36,
    paddingHorizontal: theme.spacing.md,
  },
  chipSelected: {
    backgroundColor: theme.colors.primary,
    borderColor: theme.colors.primary,
  },
  chipText: {
    color: theme.colors.mutedForeground,
    fontSize: theme.typography.caption.fontSize,
    fontWeight: "700",
  },
  chipTextSelected: {
    color: theme.colors.primaryForeground,
  },
  input: {
    backgroundColor: theme.colors.muted,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    color: theme.colors.text,
    fontSize: theme.typography.body.fontSize,
    padding: theme.spacing.md,
  },
  inputError: {
    borderColor: theme.colors.warning,
  },
  errorText: {
    color: theme.colors.warning,
    fontSize: theme.typography.caption.fontSize,
  },
  saveButton: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.md,
    marginTop: theme.spacing.sm,
    padding: theme.spacing.md,
  },
  saveButtonDisabled: {
    opacity: 0.5,
  },
  saveButtonText: {
    color: theme.colors.primaryForeground,
    fontSize: theme.typography.body.fontSize,
    fontWeight: "700",
  },
  rowAction: {
    alignItems: "center",
    flexDirection: "row",
    gap: theme.spacing.sm,
    minHeight: 44,
  },
  dangerText: {
    color: theme.colors.danger,
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "700",
  },
  warningText: {
    color: theme.colors.warning,
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "700",
  },
});
