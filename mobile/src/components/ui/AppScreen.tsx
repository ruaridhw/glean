import type { ReactNode } from "react";
import { Platform, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { theme } from "@/theme";

interface AppScreenProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  scroll?: boolean;
  testID?: string;
}

export function AppScreen({
  title,
  subtitle,
  actions,
  children,
  scroll = false,
  testID,
}: AppScreenProps) {
  const insets = useSafeAreaInsets();
  const bottomPadding = insets.bottom + (Platform.OS === "web" ? 100 : 90);

  const body = scroll ? (
    <ScrollView
      contentContainerStyle={[styles.scrollContent, { paddingBottom: bottomPadding }]}
      showsVerticalScrollIndicator={false}
    >
      {children}
    </ScrollView>
  ) : (
    <View style={[styles.body, { paddingBottom: bottomPadding }]}>{children}</View>
  );

  return (
    <SafeAreaView style={styles.container} edges={["top"]} testID={testID}>
      <View style={styles.header}>
        <View style={styles.headerText}>
          <Text style={styles.title}>{title}</Text>
          {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
        </View>
        {actions ? <View style={styles.actions}>{actions}</View> : null}
      </View>
      {body}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.background },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: theme.spacing.lg,
    paddingTop: theme.spacing.lg,
    paddingBottom: theme.spacing.md,
    backgroundColor: theme.colors.background,
  },
  headerText: { flex: 1 },
  title: { ...theme.typography.largeTitle, color: theme.colors.text },
  subtitle: { ...theme.typography.subhead, color: theme.colors.textSecondary, marginTop: 2 },
  actions: { flexDirection: "row", alignItems: "center", gap: theme.spacing.sm },
  body: { flex: 1, paddingHorizontal: theme.spacing.lg },
  scrollContent: { paddingHorizontal: theme.spacing.lg },
});
