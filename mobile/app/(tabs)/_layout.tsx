// mobile/app/(tabs)/_layout.tsx
import { Tabs } from "expo-router";
import { theme } from "@/theme";

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: theme.colors.primary,
        tabBarInactiveTintColor: theme.colors.textDisabled,
        tabBarStyle: {
          backgroundColor: theme.colors.surface,
          borderTopColor: theme.colors.border,
          borderTopWidth: 0.5,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: "600",
        },
      }}
    >
      <Tabs.Screen name="pantry/index" options={{ title: "Pantry" }} />
      <Tabs.Screen name="meals/index" options={{ title: "Meals" }} />
      <Tabs.Screen name="plan/index" options={{ title: "Plan" }} />
      <Tabs.Screen name="shop/index" options={{ title: "Shop" }} />
      <Tabs.Screen name="settings/index" options={{ title: "Settings" }} />
    </Tabs>
  );
}
