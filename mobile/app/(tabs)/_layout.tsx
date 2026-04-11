// mobile/app/(tabs)/_layout.tsx
import { Tabs } from "expo-router";
import { Text } from "react-native";
import { theme } from "@/theme";

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: theme.colors.primary,
        tabBarInactiveTintColor: theme.colors.textDisabled,
        tabBarStyle: {
          backgroundColor: theme.colors.surface,
          borderTopColor: theme.colors.border,
          borderTopWidth: 0.5,
        },
        tabBarLabelStyle: {
          fontSize: theme.typography.sectionLabel.fontSize,
          fontWeight: theme.typography.headline.fontWeight,
        },
      }}
    >
      <Tabs.Screen
        name="pantry"
        options={{ title: "Pantry", tabBarIcon: () => <Text style={{ fontSize: 20 }}>🥬</Text> }}
      />
      <Tabs.Screen
        name="meals"
        options={{ title: "Meals", tabBarIcon: () => <Text style={{ fontSize: 20 }}>🍽️</Text> }}
      />
      <Tabs.Screen
        name="plan/index"
        options={{ title: "Plan", tabBarIcon: () => <Text style={{ fontSize: 20 }}>📅</Text> }}
      />
      <Tabs.Screen
        name="shop/index"
        options={{ title: "Shop", tabBarIcon: () => <Text style={{ fontSize: 20 }}>🛒</Text> }}
      />
      <Tabs.Screen
        name="settings/index"
        options={{ title: "Settings", tabBarIcon: () => <Text style={{ fontSize: 20 }}>⚙️</Text> }}
      />
    </Tabs>
  );
}
