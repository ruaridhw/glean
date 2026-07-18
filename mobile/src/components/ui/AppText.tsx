import { StyleSheet, Text, type TextProps, type TextStyle } from "react-native";
import { fontForWeight, theme } from "@/theme";

type TypographyVariant = keyof typeof theme.typography;

interface AppTextProps extends TextProps {
  /** Applies a type-scale token from `theme.typography` (e.g. "largeTitle", "body", "sectionLabel"). */
  variant?: TypographyVariant;
}

/**
 * The app's text primitive. Always resolves to a Plus Jakarta Sans family — from an
 * explicit `fontFamily`, else the type-scale `variant`, else the effective `fontWeight`
 * (via `fontForWeight`). Prefer this over raw react-native `Text` so a style can never
 * silently fall back to the system font. Enforced by scripts/guard-text-imports.mjs.
 */
export function AppText({ variant, style, ...rest }: AppTextProps) {
  const base = variant ? (theme.typography[variant] as TextStyle) : undefined;
  const merged = (StyleSheet.flatten<TextStyle>([base, style]) ?? {}) as TextStyle;
  const fontFamily = merged.fontFamily ?? fontForWeight(merged.fontWeight);
  return <Text {...rest} style={[merged, { fontFamily }]} />;
}
