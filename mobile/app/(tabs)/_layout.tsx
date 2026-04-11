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
        options={{
          title: "Pantry",
          tabBarButtonTestID: "tabs.pantry",
          tabBarIcon: () => <Text style={{ fontSize: 20 }}>🥬</Text>,
        }}
      />
      <Tabs.Screen
        name="meals"
        options={{
          title: "Meals",
          tabBarButtonTestID: "tabs.meals",
          tabBarIcon: () => <Text style={{ fontSize: 20 }}>🍽️</Text>,
        }}
      />
      <Tabs.Screen
        name="plan/index"
        options={{
          title: "Plan",
          tabBarButtonTestID: "tabs.plan",
          tabBarIcon: () => <Text style={{ fontSize: 20 }}>📅</Text>,
        }}
      />
      <Tabs.Screen
        name="shop/index"
        options={{
          title: "Shop",
          tabBarButtonTestID: "tabs.shop",
          tabBarIcon: () => <Text style={{ fontSize: 20 }}>🛒</Text>,
        }}
      />
      <Tabs.Screen
        name="settings/index"
        options={{
          title: "Settings",
          tabBarButtonTestID: "tabs.settings",
          tabBarIcon: () => <Text style={{ fontSize: 20 }}>⚙️</Text>,
        }}
      />
      {/* Sub-screens — hide from tab bar */}
      <Tabs.Screen name="pantry/add" options={{ href: null }} />
      <Tabs.Screen name="pantry/describe" options={{ href: null }} />
      <Tabs.Screen name="pantry/manual-entry" options={{ href: null }} />
      <Tabs.Screen name="pantry/review" options={{ href: null }} />
      <Tabs.Screen name="pantry/scan" options={{ href: null }} />
      <Tabs.Screen name="pantry/scan-progress" options={{ href: null }} />
      <Tabs.Screen name="meals/search" options={{ href: null }} />
      <Tabs.Screen name="meals/[id]" options={{ href: null }} />
    </Tabs>
  );
}
