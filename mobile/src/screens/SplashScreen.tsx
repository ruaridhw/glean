import { View } from "react-native";
import { GleanMark } from "@/components/GleanMark";
import PulsingDots from "@/components/PulsingDots";
import { AppText } from "@/components/ui/AppText";
import { theme } from "@/theme";

export default function SplashScreen() {
  return (
    <View
      testID="splash-container"
      style={{
        flex: 1,
        backgroundColor: theme.colors.primary,
        justifyContent: "center",
        alignItems: "center",
        gap: theme.spacing.xxl,
      }}
    >
      <View testID="splash-logo" style={{ alignItems: "center", gap: theme.spacing.md }}>
        <GleanMark size={116} color="#fff" secondaryColor="#d8f2e0" />
        <AppText
          style={{
            fontFamily: theme.fontFamily.extrabold,
            fontSize: 34,
            letterSpacing: -1,
            color: "#fff",
          }}
        >
          glean
        </AppText>
      </View>
      <View testID="pulsing-dots-container">
        <PulsingDots color="#fff" />
      </View>
    </View>
  );
}
