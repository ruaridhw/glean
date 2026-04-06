import { StyleSheet, Text, View } from "react-native";
export default function PantryScreen() {
  return (
    <View style={s.c}>
      <Text style={s.t}>Pantry</Text>
    </View>
  );
}
const s = StyleSheet.create({
  c: { flex: 1, alignItems: "center", justifyContent: "center" },
  t: { fontSize: 24 },
});
