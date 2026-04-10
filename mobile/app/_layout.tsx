// mobile/app/_layout.tsx

import { router, Stack } from "expo-router";
import { useEffect, useState } from "react";
import { authStorage } from "@/auth/storage";
import { getDb } from "@/db/client";
import { seedDatabase } from "@/db/seed";
import { theme } from "@/theme";
import SplashScreen from "@/screens/SplashScreen";

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
    <Stack screenOptions={{ contentStyle: { backgroundColor: theme.colors.background } }}>
      <Stack.Screen name="index" options={{ headerShown: false }} />
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="sign-in" options={{ headerShown: false }} />
    </Stack>
  );
}
