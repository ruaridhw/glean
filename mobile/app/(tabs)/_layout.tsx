// mobile/app/(tabs)/_layout.tsx
import { Ionicons } from "@expo/vector-icons";
import { Tabs } from "expo-router";
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
          tabBarIcon: ({ color }) => <Ionicons name="leaf-outline" size={22} color={color} />,
        }}
      />
      <Tabs.Screen
        name="meals"
        options={{
          title: "Meals",
          tabBarButtonTestID: "tabs.meals",
          tabBarIcon: ({ color }) => <Ionicons name="restaurant-outline" size={22} color={color} />,
        }}
      />
      <Tabs.Screen
        name="plan/index"
        options={{
          title: "Plan",
          tabBarButtonTestID: "tabs.plan",
          tabBarIcon: ({ color }) => <Ionicons name="calendar-outline" size={22} color={color} />,
        }}
      />
      <Tabs.Screen
        name="shop/index"
        options={{
          title: "Shop",
          tabBarButtonTestID: "tabs.shop",
          tabBarIcon: ({ color }) => <Ionicons name="cart-outline" size={22} color={color} />,
        }}
      />
      <Tabs.Screen
        name="settings/index"
        options={{
          title: "Settings",
          tabBarButtonTestID: "tabs.settings",
          tabBarIcon: ({ color }) => <Ionicons name="settings-outline" size={22} color={color} />,
        }}
      />
      <Tabs.Screen name="shop/describe" options={{ href: null }} />
      <Tabs.Screen name="shop/review" options={{ href: null }} />
    </Tabs>
  );
}
