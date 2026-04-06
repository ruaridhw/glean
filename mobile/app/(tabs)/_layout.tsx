// mobile/app/(tabs)/_layout.tsx
import { Tabs } from "expo-router";

export default function TabsLayout() {
  return (
    <Tabs screenOptions={{ tabBarActiveTintColor: "#2a9d8f" }}>
      <Tabs.Screen name="pantry/index" options={{ title: "Pantry" }} />
      <Tabs.Screen name="meals/index" options={{ title: "Meals" }} />
      <Tabs.Screen name="plan/index" options={{ title: "Plan" }} />
      <Tabs.Screen name="shop/index" options={{ title: "Shop" }} />
      <Tabs.Screen name="settings/index" options={{ title: "Settings" }} />
    </Tabs>
  );
}
