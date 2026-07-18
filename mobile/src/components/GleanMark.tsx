import Svg, { Path } from "react-native-svg";
import { theme } from "@/theme";

interface GleanMarkProps {
  size?: number;
  /** Stem + primary leaf colour. Defaults to brand green. */
  color?: string;
  /** Secondary (back) leaf colour. Defaults to a soft green that reads on light. */
  secondaryColor?: string;
}

/**
 * The Glean brand mark — thin curved stem with two leaves (mark 2a-i).
 * viewBox 0 0 64 64. On a dark/green surface pass color="#fff" secondaryColor="#d8f2e0";
 * on light the defaults (green + #7fc79c) apply.
 */
export function GleanMark({
  size = 64,
  color = theme.colors.primary,
  secondaryColor = "#7fc79c",
}: GleanMarkProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 64 64">
      <Path d="M30.5 29C30.5 14 43 5 58 5C58 20 45.5 29 30.5 29Z" fill={secondaryColor} />
      <Path d="M33.5 36C33.5 20 21 11 6 11C6 27 19 36 33.5 36Z" fill={color} />
      <Path
        d="M32 57C29.5 48 30 39 32.5 30"
        stroke={color}
        strokeWidth={5.5}
        strokeLinecap="round"
        fill="none"
      />
    </Svg>
  );
}
