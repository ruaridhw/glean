// mobile/app/(tabs)/_layout.tsx
import { Ionicons } from "@expo/vector-icons";
import { Tabs } from "expo-router";
import { StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppText } from "@/components/ui/AppText";
import { theme } from "@/theme";

type IconName = keyof typeof Ionicons.glyphMap;

// React Navigation renders tabBarIcon inside a fixed 31x28 wrapper; a pill wider
// than that gets its glyph culled by Fabric on Android, so the wrapper must be
// sized to the pill via tabBarIconStyle.
const PILL_WIDTH = 54;
const PILL_HEIGHT = 30;

function TabIcon({ name, focused }: { name: string; focused: boolean }) {
  const iconName = (focused ? name : `${name}-outline`) as IconName;
  return (
    <View style={[styles.pill, focused && styles.pillActive]}>
      <Ionicons
        name={iconName}
        size={22}
        color={focused ? theme.colors.primaryDark : theme.colors.textDisabled}
      />
    </View>
  );
}

function TabLabel({ label, focused }: { label: string; focused: boolean }) {
  return (
    <AppText style={[styles.label, focused ? styles.labelActive : styles.labelInactive]}>
      {label}
    </AppText>
  );
}

function tabOptions(title: string, testID: string, icon: string) {
  return {
    title,
    tabBarButtonTestID: testID,
    tabBarIconStyle: { width: PILL_WIDTH, height: PILL_HEIGHT },
    tabBarIcon: ({ focused }: { focused: boolean }) => <TabIcon name={icon} focused={focused} />,
    tabBarLabel: ({ focused }: { focused: boolean }) => (
      <TabLabel label={title} focused={focused} />
    ),
  };
}

export default function TabsLayout() {
  const insets = useSafeAreaInsets();

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: theme.colors.surface,
          borderTopColor: theme.colors.border,
          borderTopWidth: 1,
          // A fixed height would discard the bottom safe-area inset and push the
          // labels under the Android gesture handle, which also swallows taps.
          height: 64 + insets.bottom,
          paddingTop: 8,
          paddingBottom: 10 + insets.bottom,
        },
        tabBarItemStyle: { gap: 2 },
      }}
    >
      <Tabs.Screen name="pantry" options={tabOptions("Pantry", "tabs.pantry", "leaf")} />
      <Tabs.Screen name="meals" options={tabOptions("Meals", "tabs.meals", "restaurant")} />
      <Tabs.Screen name="plan/index" options={tabOptions("Plan", "tabs.plan", "calendar")} />
      <Tabs.Screen name="shop" options={tabOptions("Shop", "tabs.shop", "cart")} />
      <Tabs.Screen
        name="settings/index"
        options={tabOptions("Settings", "tabs.settings", "settings")}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  pill: {
    alignItems: "center",
    borderRadius: theme.radius.pill,
    justifyContent: "center",
    paddingHorizontal: 16,
    paddingVertical: 4,
  },
  pillActive: {
    backgroundColor: theme.colors.primaryLight,
  },
  label: {
    fontSize: 11,
    fontFamily: theme.fontFamily.bold,
  },
  labelActive: {
    color: theme.colors.primaryDark,
    fontFamily: theme.fontFamily.extrabold,
  },
  labelInactive: {
    color: theme.colors.textDisabled,
  },
});
