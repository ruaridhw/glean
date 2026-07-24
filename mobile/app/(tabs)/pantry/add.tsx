// mobile/app/(tabs)/pantry/add.tsx

import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { AppText } from "@/components/ui/AppText";
import { theme } from "@/theme";

interface AddOption {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  sub: string;
  route: Parameters<typeof router.push>[0];
}

const OPTIONS: AddOption[] = [
  {
    icon: "receipt-outline",
    label: "Scan Receipt",
    sub: "Take a photo of your receipt",
    route: "/(tabs)/pantry/scan",
  },
  {
    icon: "chatbubble-outline",
    label: "Describe Purchase",
    sub: "Type what you bought",
    route: "/(tabs)/pantry/describe",
  },
  {
    icon: "create-outline",
    label: "Manual Entry",
    sub: "Add a single item",
    route: "/(tabs)/pantry/manual-entry",
  },
];

export default function AddScreen() {
  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <AppText style={styles.heading}>Add to Pantry</AppText>
      {OPTIONS.map((option) => (
        <Pressable
          key={option.label}
          style={styles.option}
          onPress={() => router.push(option.route)}
        >
          <View style={styles.iconChip}>
            <Ionicons name={option.icon} size={22} color={theme.colors.primaryDark} />
          </View>
          <View>
            <AppText style={styles.label}>{option.label}</AppText>
            <AppText style={styles.sub}>{option.sub}</AppText>
          </View>
        </Pressable>
      ))}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: theme.spacing.xl, backgroundColor: theme.colors.background },
  heading: {
    ...theme.typography.title2,
    color: theme.colors.text,
    marginBottom: theme.spacing.xl,
  },
  option: {
    flexDirection: "row",
    alignItems: "center",
    gap: theme.spacing.lg,
    padding: theme.spacing.lg,
    backgroundColor: theme.colors.card,
    borderRadius: theme.radius.lg,
    marginBottom: theme.spacing.md,
    ...theme.shadow.card,
  },
  iconChip: {
    width: 44,
    height: 44,
    borderRadius: theme.radius.pill,
    backgroundColor: theme.colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  label: {
    fontSize: 16,
    fontFamily: theme.fontFamily.bold,
    fontWeight: "700",
    color: theme.colors.text,
    marginBottom: 2,
  },
  sub: {
    fontSize: 13,
    fontFamily: theme.fontFamily.semibold,
    fontWeight: "600",
    color: theme.colors.textSecondary,
  },
});
