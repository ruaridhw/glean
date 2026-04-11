import { Ionicons } from "@expo/vector-icons";
import * as Network from "expo-network";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { theme } from "@/theme";

export function OfflineBanner() {
  const insets = useSafeAreaInsets();
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
    <View style={[s.banner, { paddingTop: insets.top + theme.spacing.sm }]} testID="offlineBanner">
      <Ionicons name="cloud-offline-outline" size={14} color={theme.colors.warning} />
      <Text style={s.text}>You're offline. Some features need internet.</Text>
    </View>
  );
}

const s = StyleSheet.create({
  banner: {
    backgroundColor: theme.colors.warningLight,
    paddingVertical: theme.spacing.sm,
    paddingHorizontal: theme.spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: theme.spacing.sm,
  },
  text: {
    fontSize: theme.typography.caption.fontSize,
    fontWeight: theme.typography.headline.fontWeight as "600",
    color: theme.colors.warning,
  },
});
