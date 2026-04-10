import * as Network from "expo-network";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { theme } from "@/theme";

export function OfflineBanner() {
  const [isOffline, setIsOffline] = useState(false);

  useEffect(() => {
    let mounted = true;

    async function check() {
      const state = await Network.getNetworkStateAsync();
      if (mounted) setIsOffline(!state.isConnected);
    }

    check();
    const interval = setInterval(check, 5000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  if (!isOffline) return null;

  return (
    <View style={s.banner} testID="offlineBanner">
      <Text style={s.text}>You're offline. Some features need internet.</Text>
    </View>
  );
}

const s = StyleSheet.create({
  banner: {
    backgroundColor: theme.colors.warningLight,
    paddingVertical: theme.spacing.sm,
    paddingHorizontal: theme.spacing.lg,
    alignItems: "center",
  },
  text: {
    fontSize: theme.typography.caption.fontSize,
    fontWeight: theme.typography.headline.fontWeight as "600",
    color: theme.colors.warning,
  },
});
