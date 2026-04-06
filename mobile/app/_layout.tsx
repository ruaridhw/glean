// mobile/app/_layout.tsx

import { router, Stack } from "expo-router";
import { useEffect, useState } from "react";
import { authStorage } from "@/auth/storage";
import { getDb } from "@/db/client";
import { seedDatabase } from "@/db/seed";

export default function RootLayout() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const db = await getDb();
        await seedDatabase(db);
        const authenticated = await authStorage.hasTokens();
        if (!authenticated) {
          router.replace("/sign-in");
        }
      } finally {
        setReady(true);
      }
    })();
  }, []);

  if (!ready) return null;

  return (
    <Stack>
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="sign-in" options={{ headerShown: false }} />
    </Stack>
  );
}
