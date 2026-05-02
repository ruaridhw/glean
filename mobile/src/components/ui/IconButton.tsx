import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, type PressableProps, type StyleProp, type ViewStyle } from "react-native";
import { hapticImpact } from "@/platform/haptics";
import { theme } from "@/theme";

interface IconButtonProps extends Omit<PressableProps, "children" | "style"> {
  icon: keyof typeof Ionicons.glyphMap;
  accessibilityLabel: string;
  color?: string;
  backgroundColor?: string;
  size?: number;
  style?: StyleProp<ViewStyle>;
}

export function IconButton({
  icon,
  accessibilityLabel,
  color = theme.colors.text,
  backgroundColor = theme.colors.muted,
  size = 20,
  onPress,
  style,
  ...props
}: IconButtonProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      hitSlop={8}
      style={[styles.button, { backgroundColor }, style]}
      onPress={(event) => {
        void hapticImpact("light");
        onPress?.(event);
      }}
      {...props}
    >
      <Ionicons name={icon} size={size} color={color} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    alignItems: "center",
    borderRadius: theme.radius.pill,
    height: 40,
    justifyContent: "center",
    width: 40,
  },
});
