// mobile/app/(tabs)/settings/index.tsx

import { Ionicons } from "@expo/vector-icons";
import Slider from "@react-native-community/slider";
import { File, Paths } from "expo-file-system";
import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Alert, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { apiClient } from "@/api/client";
import { useAuthSession } from "@/auth/session";
import { GleanMark } from "@/components/GleanMark";
import { AppScreen } from "@/components/ui/AppScreen";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatsRow } from "@/components/ui/StatsRow";
import { getUserConfig, saveUserConfig } from "@/db/config";
import { toRequiredSubmittedText } from "@/normalization/text-input";
import { hapticImpact } from "@/platform/haptics";
import {
  DIETARY_OPTIONS,
  getToleranceLabel,
  SETTINGS_OPTION_RANGES,
  validateBoundedInteger,
} from "@/settings/presentation";
import { theme } from "@/theme";
import { showError } from "@/utils/toast";

const DINNERS_RANGE = SETTINGS_OPTION_RANGES.dinnersPerWeek;
const SERVINGS_RANGE = SETTINGS_OPTION_RANGES.defaultServings;
const MAX_TIME_RANGE = SETTINGS_OPTION_RANGES.maxActiveTimeMins;

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
  const { signOut } = useAuthSession();
  const [configId, setConfigId] = useState("");
  const [tolerance, setTolerance] = useState(0.5);
  const [servings, setServings] = useState(2);
  const [mealsPerWeek, setMealsPerWeek] = useState(5);
  const [dietaryFlags, setDietaryFlags] = useState<string[]>([]);
  const [maxTime, setMaxTime] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [maxTimeError, setMaxTimeError] = useState<string | null>(null);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    setLoadFailed(false);
    try {
      const config = await getUserConfig();
      setConfigId(config.id);
      setTolerance(config.purchase_tolerance);
      setServings(config.preferred_servings);
      setMealsPerWeek(config.meals_per_week);
      setDietaryFlags(config.dietary_flags);
      setMaxTime(config.max_active_time_mins ? String(config.max_active_time_mins) : "");
    } catch (error) {
      console.error("[settings] config load failed:", error);
      setLoadFailed(true);
      showError("Could not load settings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  function handleMaxTimeChange(value: string) {
    setMaxTime(value);
    const normalizedValue = toRequiredSubmittedText(value);
    if (!normalizedValue) {
      setMaxTimeError(null);
      return;
    }
    setMaxTimeError(
      validateBoundedInteger(
        normalizedValue,
        MAX_TIME_RANGE.min,
        MAX_TIME_RANGE.max,
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
    if (loading || !configId || maxTimeError) return;
    const normalizedMaxTime = toRequiredSubmittedText(maxTime);
    await saveUserConfig({
      id: configId,
      purchase_tolerance: tolerance,
      preferred_servings: servings,
      meals_per_week: mealsPerWeek,
      dietary_flags: dietaryFlags,
      max_active_time_mins: normalizedMaxTime ? parseInt(normalizedMaxTime, 10) : null,
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
        actions={<GleanMark size={36} />}
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

  if (loadFailed) {
    return (
      <AppScreen
        title="Settings"
        subtitle="Preferences and account"
        actions={<GleanMark size={36} />}
        scroll
        keyboardAvoiding
        testID="settings.screen"
      >
        <Card style={styles.sectionCard}>
          <Text style={styles.fieldTitle}>Could not load settings.</Text>
          <Text style={styles.description}>Check your connection and try again.</Text>
          <Pressable accessibilityRole="button" style={styles.retryButton} onPress={loadConfig}>
            <Text style={styles.retryButtonText}>Try again</Text>
          </Pressable>
        </Card>
      </AppScreen>
    );
  }

  return (
    <AppScreen
      title="Settings"
      subtitle="Preferences and account"
      actions={<GleanMark size={36} />}
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

      <SectionHeader title="Preferences" />

      <Card style={styles.sectionCard}>
        <View style={styles.fieldHeader}>
          <Text style={styles.fieldTitle}>Purchase tolerance</Text>
          <Badge tone="primary" label={`${Math.round(tolerance * 100)}%`} />
        </View>
        <Text style={styles.description}>{getToleranceLabel(tolerance)}</Text>
        <Slider
          testID="settings.toleranceSlider"
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
        <View style={styles.fieldHeader}>
          <Text style={styles.fieldTitle}>Dinners per week</Text>
          <Badge tone="primary" label={String(mealsPerWeek)} />
        </View>
        <Slider
          testID="settings.dinnersSlider"
          style={styles.slider}
          minimumValue={DINNERS_RANGE.min}
          maximumValue={DINNERS_RANGE.max}
          step={1}
          value={mealsPerWeek}
          onValueChange={(value) => setMealsPerWeek(Math.round(value))}
          minimumTrackTintColor={theme.colors.primary}
          thumbTintColor={theme.colors.primary}
        />
        <View style={styles.sliderScale}>
          <Text style={styles.sliderScaleText}>{DINNERS_RANGE.min}</Text>
          <Text style={styles.sliderScaleText}>{DINNERS_RANGE.max}</Text>
        </View>
      </Card>

      <Card style={styles.sectionCard}>
        <View style={styles.fieldHeader}>
          <Text style={styles.fieldTitle}>Default servings</Text>
          <Badge tone="primary" label={String(servings)} />
        </View>
        <Slider
          testID="settings.servingsSlider"
          style={styles.slider}
          minimumValue={SERVINGS_RANGE.min}
          maximumValue={SERVINGS_RANGE.max}
          step={1}
          value={servings}
          onValueChange={(value) => setServings(Math.round(value))}
          minimumTrackTintColor={theme.colors.primary}
          thumbTintColor={theme.colors.primary}
        />
        <View style={styles.sliderScale}>
          <Text style={styles.sliderScaleText}>{SERVINGS_RANGE.min}</Text>
          <Text style={styles.sliderScaleText}>{SERVINGS_RANGE.max}</Text>
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
        <Text style={styles.saveButtonText}>Save settings</Text>
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
    fontFamily: theme.fontFamily.semibold,
  },
  sectionCard: {
    gap: theme.spacing.md,
    marginBottom: theme.spacing.md,
  },
  fieldHeader: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  fieldTitle: {
    color: theme.colors.text,
    fontSize: 15,
    fontWeight: "800",
    fontFamily: theme.fontFamily.extrabold,
  },
  description: {
    color: theme.colors.textSecondary,
    fontSize: theme.typography.caption.fontSize,
    fontFamily: theme.fontFamily.semibold,
    lineHeight: 18,
  },
  slider: {
    height: 40,
  },
  sliderScale: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: -theme.spacing.sm,
  },
  sliderScaleText: {
    color: theme.colors.mutedForeground,
    fontSize: theme.typography.caption.fontSize,
    fontWeight: "700",
    fontFamily: theme.fontFamily.bold,
  },
  input: {
    backgroundColor: theme.colors.muted,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    color: theme.colors.text,
    fontSize: theme.typography.body.fontSize,
    fontFamily: theme.fontFamily.regular,
    padding: theme.spacing.md,
  },
  inputError: {
    borderColor: theme.colors.warning,
  },
  errorText: {
    color: theme.colors.warning,
    fontSize: theme.typography.caption.fontSize,
    fontFamily: theme.fontFamily.semibold,
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
    fontFamily: theme.fontFamily.bold,
  },
  chipTextSelected: {
    color: theme.colors.primaryForeground,
  },
  saveButton: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.pill,
    marginTop: theme.spacing.sm,
    padding: theme.spacing.lg,
    ...theme.shadow.fab,
  },
  saveButtonDisabled: {
    opacity: 0.5,
  },
  saveButtonText: {
    color: theme.colors.primaryForeground,
    fontSize: 15,
    fontWeight: "800",
    fontFamily: theme.fontFamily.extrabold,
  },
  retryButton: {
    alignItems: "center",
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.pill,
    padding: theme.spacing.md,
  },
  retryButtonText: {
    color: theme.colors.primaryForeground,
    fontSize: theme.typography.body.fontSize,
    fontWeight: "700",
    fontFamily: theme.fontFamily.bold,
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
    fontWeight: "800",
    fontFamily: theme.fontFamily.extrabold,
  },
  warningText: {
    color: theme.colors.warning,
    fontSize: theme.typography.subhead.fontSize,
    fontWeight: "800",
    fontFamily: theme.fontFamily.extrabold,
  },
});
