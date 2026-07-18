// mobile/app/(tabs)/_layout.tsx
import { Ionicons } from "@expo/vector-icons";
import { Tabs } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { theme } from "@/theme";

type IconName = keyof typeof Ionicons.glyphMap;

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
    <Text style={[styles.label, focused ? styles.labelActive : styles.labelInactive]}>{label}</Text>
  );
}

function tabOptions(title: string, testID: string, icon: string) {
  return {
    title,
    tabBarButtonTestID: testID,
    tabBarIcon: ({ focused }: { focused: boolean }) => <TabIcon name={icon} focused={focused} />,
    tabBarLabel: ({ focused }: { focused: boolean }) => (
      <TabLabel label={title} focused={focused} />
    ),
  };
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: theme.colors.surface,
          borderTopColor: theme.colors.border,
          borderTopWidth: 1,
          height: 64,
          paddingTop: 8,
          paddingBottom: 10,
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
