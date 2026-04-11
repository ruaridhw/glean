// mobile/app/(tabs)/pantry/manual-entry.tsx

import { router } from "expo-router";
import { useState } from "react";
import { Alert, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { resolveOrCreateIngredient } from "@/db/ingredients";
import { upsertPantryItem } from "@/db/pantry";
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
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, backgroundColor: "#fff" },
  heading: { fontSize: 22, fontWeight: "700", marginBottom: 20 },
  input: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    marginBottom: 12,
  },
  row: { flexDirection: "row", marginBottom: 12 },
  unitRow: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  unitBtn: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  unitBtnActive: { borderColor: "#2a9d8f", backgroundColor: "#2a9d8f" },
  unitText: { color: "#444", fontSize: 13 },
  unitTextActive: { color: "#fff", fontSize: 13 },
  button: {
    backgroundColor: "#2a9d8f",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
    marginTop: 8,
  },
  buttonText: { color: "#fff", fontWeight: "600", fontSize: 16 },
});
