// mobile/app/_layout.tsx

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { router, Stack } from "expo-router";
import { useEffect, useState } from "react";
import { Platform, UIManager } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { authStorage } from "@/auth/storage";
import { OfflineBanner } from "@/components/ui/OfflineBanner";
import { Toast, toastConfig } from "@/components/ui/Toast";
import { getDb } from "@/db/client";
import { seedDatabase } from "@/db/seed";
import SplashScreen from "@/screens/SplashScreen";
import { theme } from "@/theme";

const isFabricEnabled = Boolean(
  (globalThis as typeof globalThis & { nativeFabricUIManager?: unknown }).nativeFabricUIManager,
);

if (
  Platform.OS === "android" &&
  !isFabricEnabled &&
  UIManager.setLayoutAnimationEnabledExperimental
) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 0 },
    mutations: { retry: 0 },
  },
});

export default function RootLayout() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        console.log("[layout] starting db init");
        const db = await getDb();
        console.log("[layout] db ready, seeding");
        await seedDatabase(db);
        console.log("[layout] seed done, checking auth");
        const authenticated = await authStorage.hasTokens();
        console.log("[layout] authenticated:", authenticated);
        if (!authenticated) {
          router.replace("/sign-in");
        }
      } catch (e) {
        console.error("[layout] init error:", e);
      } finally {
        setReady(true);
      }
    })();
  }, []);

  if (!ready) return <SplashScreen />;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <QueryClientProvider client={queryClient}>
        <OfflineBanner />
        <Stack screenOptions={{ contentStyle: { backgroundColor: theme.colors.background } }}>
          <Stack.Screen name="index" options={{ headerShown: false }} />
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen name="sign-in" options={{ headerShown: false }} />
        </Stack>
        <Toast config={toastConfig} position="bottom" bottomOffset={80} />
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}
