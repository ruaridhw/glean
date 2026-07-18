import { forwardRef } from "react";
import { StyleSheet, TextInput, type TextInputProps, type TextStyle } from "react-native";
import { fontForWeight, theme } from "@/theme";

/**
 * The app's text-input primitive — same font guarantee as {@link AppText}: the entered
 * text always renders in a Plus Jakarta Sans family, and the placeholder defaults to the
 * disabled-text token. Prefer this over raw react-native `TextInput`.
 */
export const AppTextInput = forwardRef<TextInput, TextInputProps>(function AppTextInput(
  { style, placeholderTextColor, ...rest },
  ref,
) {
  const merged = (StyleSheet.flatten<TextStyle>(style) ?? {}) as TextStyle;
  const fontFamily = merged.fontFamily ?? fontForWeight(merged.fontWeight);
  return (
    <TextInput
      ref={ref}
      placeholderTextColor={placeholderTextColor ?? theme.colors.textDisabled}
      {...rest}
      style={[merged, { fontFamily }]}
    />
  );
});
