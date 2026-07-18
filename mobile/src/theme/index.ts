// Plus Jakarta Sans — loaded in app/_layout.tsx via @expo-google-fonts/plus-jakarta-sans.
// React Native picks the weight from the family name, so styles must set the family
// (not just fontWeight). Access via `theme.fontFamily.*` or spread a `theme.typography.*` token.
const fontFamily = {
  regular: "PlusJakartaSans_400Regular",
  medium: "PlusJakartaSans_500Medium",
  semibold: "PlusJakartaSans_600SemiBold",
  bold: "PlusJakartaSans_700Bold",
  extrabold: "PlusJakartaSans_800ExtraBold",
} as const;

export const theme = {
  fontFamily,
  colors: {
    background: "#f7f5ee", // warm oat, slightly greener
    surface: "#ffffff", // tab bar / raised surfaces (now white)
    card: "#ffffff",
    border: "#ebe6d9",
    borderStrong: "#d6d0bf", // stronger border for dashed / checkbox outlines
    muted: "#efece1",
    mutedForeground: "#85806f", // olive-grey
    primary: "#2e9d63", // brand green
    primaryDark: "#1c6b41", // text-on-tint / active tab
    primaryLight: "#e3f2e7",
    primaryForeground: "#ffffff",
    secondary: "#efece1",
    accent: "#de8a3f",
    warning: "#a8631f", // text tone; pair with warningLight
    warningLight: "#fbe9d6",
    success: "#1c6b41",
    successLight: "#e3f2e7",
    danger: "#b13c25", // muted brick, on dangerLight
    dangerLight: "#f9ded8",
    text: "#26362b", // deep green-black
    textSecondary: "#85806f",
    textDisabled: "#b3ae9c",
    ink: "#26362b", // dark surfaces (checkout bar, selected filter chip)
  },
  // Tinted [bg, fg] pairs — replace the old saturated category dots.
  categoryColors: {
    vegetables: { bg: "#e3f2e7", fg: "#1c6b41" },
    fruit: { bg: "#e3f2e7", fg: "#1c6b41" },
    protein: { bg: "#f9ded8", fg: "#b13c25" },
    dairy: { bg: "#e0ebf2", fg: "#3e6a8c" },
    carbohydrates: { bg: "#f4e6cf", fg: "#96660f" },
    fats: { bg: "#f4e6cf", fg: "#96660f" },
    condiments: { bg: "#f4e6cf", fg: "#96660f" },
    frozen: { bg: "#e0ebf2", fg: "#3e6a8c" },
    other: { bg: "#efece1", fg: "#85806f" },
  },
  expiryColors: {
    expired: "#b13c25",
    soon: "#a8631f",
    later: "#a8631f",
    none: "#efece1",
  },
  spacing: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
  radius: { sm: 8, md: 14, lg: 16, xl: 20, pill: 999 },
  shadow: {
    // Borderless cards: soft ambient shadow.
    card: {
      shadowColor: "#26362b",
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.06,
      shadowRadius: 10,
      elevation: 2,
    },
    sheet: {
      shadowColor: "#26362b",
      shadowOffset: { width: 0, height: -2 },
      shadowOpacity: 0.1,
      shadowRadius: 20,
      elevation: 8,
    },
    fab: {
      shadowColor: "#2e9d63",
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.3,
      shadowRadius: 12,
      elevation: 8,
    },
  },
  typography: {
    largeTitle: {
      fontSize: 30,
      fontWeight: "800",
      letterSpacing: -0.6,
      fontFamily: fontFamily.extrabold,
    },
    title2: { fontSize: 22, fontWeight: "700", fontFamily: fontFamily.bold },
    headline: { fontSize: 17, fontWeight: "700", fontFamily: fontFamily.bold },
    body: { fontSize: 16, fontWeight: "400", fontFamily: fontFamily.regular },
    subhead: { fontSize: 14, fontWeight: "600", fontFamily: fontFamily.semibold },
    caption: { fontSize: 12, fontWeight: "600", fontFamily: fontFamily.semibold },
    sectionLabel: {
      fontSize: 12,
      fontWeight: "800",
      textTransform: "uppercase",
      letterSpacing: 0.96,
      color: "#6d6a5c",
      fontFamily: fontFamily.extrabold,
    },
  },
} as const;
