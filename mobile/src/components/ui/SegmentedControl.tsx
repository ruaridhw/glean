import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { hapticImpact } from "@/platform/haptics";
import { theme } from "@/theme";

interface SegmentedControlOption<T extends string> {
  value: T;
  label: string;
  icon?: keyof typeof Ionicons.glyphMap;
}

interface SegmentedControlProps<T extends string> {
  value: T;
  options: Array<SegmentedControlOption<T>>;
  onChange: (value: T) => void;
  testID?: string;
}

export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
  testID,
}: SegmentedControlProps<T>) {
  return (
    <View style={styles.container} testID={testID}>
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value}
            accessibilityRole="button"
            accessibilityState={{ selected }}
            style={[styles.option, selected && styles.optionSelected]}
            onPress={() => {
              void hapticImpact("light");
              onChange(option.value);
            }}
          >
            {option.icon ? (
              <Ionicons
                name={option.icon}
                size={16}
                color={selected ? theme.colors.primaryDark : theme.colors.mutedForeground}
              />
            ) : null}
            <Text style={[styles.label, selected && styles.labelSelected]}>{option.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: theme.colors.muted,
    borderRadius: theme.radius.pill,
    flexDirection: "row",
    gap: theme.spacing.xs,
    padding: theme.spacing.xs,
  },
  option: {
    alignItems: "center",
    borderRadius: theme.radius.pill,
    flex: 1,
    flexDirection: "row",
    gap: 6,
    justifyContent: "center",
    minHeight: 42,
  },
  optionSelected: {
    backgroundColor: theme.colors.card,
    ...theme.shadow.card,
  },
  label: {
    color: theme.colors.mutedForeground,
    fontSize: 14,
    fontWeight: "800",
    fontFamily: theme.fontFamily.extrabold,
  },
  labelSelected: {
    color: theme.colors.primaryDark,
  },
});
