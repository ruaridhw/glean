import type { ReactNode } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  type ScrollViewProps,
  StyleSheet,
  View,
} from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { theme } from "@/theme";
import { AppText } from "./AppText";
import { Badge } from "./Badge";

export interface AppScreenChip {
  label: string;
  tone?: "neutral" | "primary" | "warning" | "danger";
}

interface AppScreenProps {
  title: string;
  subtitle?: string;
  /** Pill chips shown under the title (e.g. count / expiring). Replaces subtitle when set. */
  chips?: AppScreenChip[];
  actions?: ReactNode;
  children: ReactNode;
  scroll?: boolean;
  keyboardAvoiding?: boolean;
  keyboardDismissMode?: ScrollViewProps["keyboardDismissMode"];
  contentPaddingBottom?: number;
  testID?: string;
}

export function AppScreen({
  title,
  subtitle,
  chips,
  actions,
  children,
  scroll = false,
  keyboardAvoiding = false,
  keyboardDismissMode = "on-drag",
  contentPaddingBottom,
  testID,
}: AppScreenProps) {
  const insets = useSafeAreaInsets();
  const bottomPadding = insets.bottom + (Platform.OS === "web" ? 100 : 90);
  const resolvedBottomPadding = contentPaddingBottom ?? bottomPadding;

  const body = scroll ? (
    <ScrollView
      contentContainerStyle={[styles.scrollContent, { paddingBottom: resolvedBottomPadding }]}
      keyboardDismissMode={keyboardDismissMode}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
    >
      {children}
    </ScrollView>
  ) : (
    <View style={[styles.body, { paddingBottom: resolvedBottomPadding }]}>{children}</View>
  );

  const screen = (
    <SafeAreaView style={styles.container} edges={["top"]} testID={testID}>
      <View style={styles.header}>
        <View style={styles.headerText}>
          <AppText style={styles.title}>{title}</AppText>
          {chips && chips.length > 0 ? (
            <View style={styles.chips}>
              {chips.map((chip) => (
                <Badge key={chip.label} label={chip.label} tone={chip.tone ?? "primary"} />
              ))}
            </View>
          ) : subtitle ? (
            <AppText style={styles.subtitle}>{subtitle}</AppText>
          ) : null}
        </View>
        {actions ? <View style={styles.actions}>{actions}</View> : null}
      </View>
      {body}
    </SafeAreaView>
  );

  if (!keyboardAvoiding) return screen;

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      style={styles.container}
    >
      {screen}
    </KeyboardAvoidingView>
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
  headerText: { flex: 1, gap: 6 },
  title: { ...theme.typography.largeTitle, color: theme.colors.text },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  subtitle: { ...theme.typography.subhead, color: theme.colors.textSecondary },
  actions: { flexDirection: "row", alignItems: "center", gap: theme.spacing.sm },
  body: { flex: 1, paddingHorizontal: theme.spacing.lg },
  scrollContent: { paddingHorizontal: theme.spacing.lg },
});
