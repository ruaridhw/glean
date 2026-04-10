import { Image, View } from "react-native";
import PulsingDots from "@/components/PulsingDots";
import { theme } from "@/theme";

export default function SplashScreen() {
  return (
    <View
      testID="splash-container"
      style={{
        flex: 1,
        backgroundColor: theme.colors.background,
        justifyContent: "center",
        alignItems: "center",
        gap: theme.spacing.xxl,
      }}
    >
      <Image
        testID="splash-logo"
        source={require("../../assets/glean-logo.png")}
        style={{
          width: 180,
          height: 180,
          resizeMode: "contain",
        }}
      />
      <View testID="pulsing-dots-container">
        <PulsingDots color={theme.colors.primary} />
      </View>
    </View>
  );
}
