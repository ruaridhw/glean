// mobile/app/(tabs)/pantry/manual-entry.tsx

import { router } from "expo-router";
import { useState } from "react";
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { resolveOrCreateIngredient } from "@/db/ingredients";
import { upsertPantryItem } from "@/db/pantry";
import { theme } from "@/theme";
import { showSuccess } from "@/utils/toast";

const UNITS = ["g", "ml", "units", "kg", "l"];

export default function ManualEntryScreen() {
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState("g");
  const [saving, setSaving] = useState(false);

  async function save() {
    const qty = parseFloat(quantity);
    if (!name.trim() || Number.isNaN(qty) || qty <= 0) {
      Alert.alert("Please enter a name and valid quantity.");
      return;
    }
    setSaving(true);
    try {
      const ingredientId = await resolveOrCreateIngredient({
        canonical_name: name.trim().toLowerCase(),
      });
      await upsertPantryItem({ ingredient_id: ingredientId, quantity: qty, unit });
      showSuccess("Added to pantry");
      router.replace("/(tabs)/pantry");
    } catch {
      Alert.alert("Failed to save item.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      style={styles.keyboardView}
    >
      <SafeAreaView style={styles.container} edges={["top"]}>
        <Text style={styles.heading}>Add item</Text>
        <TextInput
          style={styles.input}
          value={name}
          onChangeText={setName}
          placeholder="Ingredient name"
          testID="manualEntry.nameInput"
          autoFocus
        />
        <View style={styles.row}>
          <TextInput
            style={[styles.input, { flex: 1, marginRight: 8 }]}
            value={quantity}
            onChangeText={setQuantity}
            placeholder="Quantity"
            testID="manualEntry.quantityInput"
            keyboardType="numeric"
          />
          <View style={styles.unitRow}>
            {UNITS.map((u) => (
              <Pressable
                key={u}
                style={[styles.unitBtn, unit === u && styles.unitBtnActive]}
                onPress={() => setUnit(u)}
              >
                <Text style={unit === u ? styles.unitTextActive : styles.unitText}>{u}</Text>
              </Pressable>
            ))}
          </View>
        </View>
        <Pressable
          style={styles.button}
          testID="manualEntry.saveButton"
          onPress={save}
          disabled={saving}
        >
          <Text style={styles.buttonText}>Add to Pantry</Text>
        </Pressable>
      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  keyboardView: { flex: 1, backgroundColor: theme.colors.background },
  container: { flex: 1, padding: theme.spacing.xl },
  heading: {
    fontSize: theme.typography.title2.fontSize,
    fontWeight: theme.typography.title2.fontWeight,
    color: theme.colors.text,
    marginBottom: 20,
  },
  input: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.sm,
    padding: theme.spacing.md,
    fontSize: 16,
    marginBottom: theme.spacing.md,
    color: theme.colors.text,
    backgroundColor: theme.colors.card,
  },
  row: { flexDirection: "row", marginBottom: theme.spacing.md },
  unitRow: { flexDirection: "row", flexWrap: "wrap", gap: theme.spacing.xs + 2 },
  unitBtn: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.sm,
    paddingHorizontal: 10,
    paddingVertical: 6,
    minHeight: 36,
    justifyContent: "center",
  },
  unitBtnActive: { borderColor: theme.colors.primary, backgroundColor: theme.colors.primary },
  unitText: { color: theme.colors.text, fontSize: 13 },
  unitTextActive: { color: theme.colors.card, fontSize: 13 },
  button: {
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.sm,
    padding: 14,
    alignItems: "center",
    marginTop: theme.spacing.sm,
    minHeight: 44,
    justifyContent: "center",
  },
  buttonText: {
    color: theme.colors.card,
    fontWeight: theme.typography.headline.fontWeight as "600",
    fontSize: 16,
  },
});
