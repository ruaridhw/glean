import { StyleSheet, Text, View } from "react-native";
import { theme } from "@/theme";

export default function MealsScreen() {
  return (
    <View style={s.container}>
      <Text style={s.title}>Meals</Text>
    </View>
  );
}

const s = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
    alignItems: "center",
    justifyContent: "center",
  },
  title: {
    fontSize: theme.typography.largeTitle.fontSize,
    fontWeight: theme.typography.largeTitle.fontWeight,
    color: theme.colors.text,
  },
});
