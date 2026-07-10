// mobile/app/_layout.tsx

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { router, Stack } from "expo-router";
import { useEffect, useState } from "react";
import { Platform, UIManager } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { AuthProvider, useAuthSession } from "@/auth/session";
import { OfflineBanner } from "@/components/ui/OfflineBanner";
import { Toast, toastConfig } from "@/components/ui/Toast";
import { getDb } from "@/db/client";
import { seedDatabase } from "@/db/seed";
import { hasCompletedOnboarding } from "@/onboarding/storage";
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

function RootNavigator() {
  const { isAuthenticated, isLoading } = useAuthSession();
  const [onboardingComplete, setOnboardingComplete] = useState<boolean | null>(null);

  useEffect(() => {
    let mounted = true;

    if (isLoading) return;

    if (!isAuthenticated) {
      setOnboardingComplete(null);
      return;
    }

    setOnboardingComplete(null);
    hasCompletedOnboarding()
      .then((complete) => {
        if (!mounted) return;
        setOnboardingComplete(complete);
        if (!complete) router.replace("/onboarding");
      })
      .catch((error: unknown) => {
        console.warn("[layout] onboarding check failed:", error);
        if (!mounted) return;
        setOnboardingComplete(false);
        router.replace("/onboarding");
      });

    return () => {
      mounted = false;
    };
  }, [isAuthenticated, isLoading]);

  if (isLoading) return <SplashScreen />;
  if (isAuthenticated && onboardingComplete == null) return <SplashScreen />;

  return (
    <Stack screenOptions={{ contentStyle: { backgroundColor: theme.colors.background } }}>
      <Stack.Protected guard={!isAuthenticated}>
        <Stack.Screen name="sign-in" options={{ headerShown: false }} />
        <Stack.Screen name="auth/callback" options={{ headerShown: false }} />
      </Stack.Protected>
      <Stack.Protected guard={isAuthenticated}>
        <Stack.Screen name="onboarding" options={{ headerShown: false }} />
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let mounted = true;

    (async () => {
      try {
        console.log("[layout] starting db init");
        const db = await getDb();
        console.log("[layout] db ready, seeding");
        await seedDatabase(db);
        console.log("[layout] seed done");
      } catch (e) {
        console.error("[layout] init error:", e);
      } finally {
        if (mounted) setReady(true);
      }
    })();

    return () => {
      mounted = false;
    };
  }, []);

  if (!ready) return <SplashScreen />;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <OfflineBanner />
          <RootNavigator />
          <Toast config={toastConfig} position="bottom" bottomOffset={80} />
        </AuthProvider>
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}
