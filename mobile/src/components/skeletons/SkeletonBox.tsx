import { useEffect, useRef } from "react";
import { Animated, type DimensionValue, type StyleProp, type ViewStyle } from "react-native";
import { theme } from "@/theme";

export function SkeletonBox({
  width,
  height,
  style,
}: {
  width: DimensionValue;
  height: number;
  style?: StyleProp<ViewStyle>;
}) {
  const opacity = useRef(new Animated.Value(0.3)).current;

  useEffect(() => {
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
        }),
        Animated.timing(opacity, {
          toValue: 0.3,
          duration: 1000,
          useNativeDriver: true,
        }),
      ]),
    );
    anim.start();
    return () => anim.stop();
  }, [opacity]);

  return (
    <Animated.View
      style={[
        {
          width,
          height,
          backgroundColor: theme.colors.surface,
          borderRadius: theme.radius.sm,
          opacity,
        },
        style,
      ]}
    />
  );
}
