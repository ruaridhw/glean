import 'package:flutter/material.dart';

import 'tokens.dart';

/// Brand hex constants used exactly once, to build [gleanLightTheme]. This is
/// deliberately the *only* file in the design system that references raw
/// hex — everywhere else (including feature code) reaches the brand through
/// `Theme.of(context)` (AC-DS-03). Values are ported 1:1 from
/// `mobile/src/theme/index.ts`.
class _Brand {
  const _Brand._();

  static const Color background = Color(
    0xFFF7F5EE,
  ); // warm oat, slightly greener
  static const Color surface = Color(0xFFFFFFFF); // card / raised surfaces
  static const Color border = Color(0xFFEBE6D9);
  static const Color borderStrong = Color(0xFFD6D0BF);
  static const Color muted = Color(0xFFEFECE1);
  static const Color mutedForeground = Color(0xFF85806F); // olive-grey
  static const Color primary = Color(0xFF2E9D63); // brand green
  static const Color primaryDark = Color(
    0xFF1C6B41,
  ); // text-on-tint / active tab
  static const Color primaryLight = Color(0xFFE3F2E7);
  static const Color accent = Color(0xFFDE8A3F);
  // warning/warningLight and success/successLight have no ColorScheme role
  // (see tokens.dart's AppTokens.standard, which owns those literals) — not
  // duplicated here since nothing in this file would reference them.
  static const Color danger = Color(0xFFB13C25); // muted brick
  static const Color dangerLight = Color(0xFFF9DED8);
  static const Color text = Color(0xFF26362B); // deep green-black
  static const Color textSecondary = Color(0xFF85806F);
  static const Color textDisabled = Color(0xFFB3AE9C);
  static const Color ink = Color(0xFF26362B); // dark surfaces
}

/// Family name declared in `pubspec.yaml` with weight descriptors 400–800
/// (AC-BUILD-03). Because Flutter resolves `fontWeight` against those
/// descriptors — unlike React Native, which resolves weight from the family
/// *name* — a single family plus plain `fontWeight` is enough; no `AppText`
/// primitive is needed to enforce it (AC-DS-08).
const String _fontFamily = 'PlusJakartaSans';

/// Maps the RN `theme.colors` palette onto [ColorScheme], builds a
/// [TextTheme] off the RN `theme.typography` scale, and themes every relevant
/// built-in centrally — the core inversion versus the RN app (which must
/// *wrap* every primitive because React Native ships no themed ones;
/// FLUTTER_MIGRATION.md §4).
///
/// Dark mode is explicitly out of scope (§1), but every token below is only
/// ever reached via `Theme.of(context)` (AC-DS-03), so adding a
/// `gleanDarkTheme` later is a second `ThemeData`, not a codebase-wide
/// refactor.
ThemeData get gleanLightTheme {
  const ColorScheme colorScheme = ColorScheme.light(
    brightness: Brightness.light,
    primary: _Brand.primary,
    onPrimary: Colors.white,
    primaryContainer: _Brand.primaryLight,
    onPrimaryContainer: _Brand.primaryDark,
    // RN's `accent` (a warm orange) has no dedicated ColorScheme role of its
    // own; `secondary` is the closest Material slot for "the other brand
    // colour used sparingly for emphasis".
    secondary: _Brand.accent,
    onSecondary: Colors.white,
    secondaryContainer: Color(0xFFF4E6CF),
    onSecondaryContainer: Color(0xFF96660F),
    // The RN palette has exactly two brand hues (green + orange) — no third.
    // Leaving `tertiary` unset would default to an unbranded Material teal
    // wherever a built-in falls back to it, so it deliberately reuses
    // primary's darker tone rather than introduce an off-brand colour.
    tertiary: _Brand.primaryDark,
    onTertiary: Colors.white,
    tertiaryContainer: _Brand.primaryLight,
    onTertiaryContainer: _Brand.primaryDark,
    // RN's `danger`/`dangerLight` map directly onto `error`/`errorContainer`
    // — deliberately not also duplicated into AppTokens (see tokens.dart).
    error: _Brand.danger,
    onError: Colors.white,
    errorContainer: _Brand.dangerLight,
    onErrorContainer: _Brand.danger,
    surface: _Brand.surface,
    onSurface: _Brand.text,
    surfaceContainerHighest: _Brand.muted,
    onSurfaceVariant: _Brand.mutedForeground,
    outline: _Brand.border,
    outlineVariant: _Brand.borderStrong,
    shadow: _Brand.text,
    inverseSurface: _Brand.ink,
    onInverseSurface: Colors.white,
    surfaceTint:
        Colors.transparent, // no M3 elevation tint — flat brand surfaces
  );

  final TextTheme textTheme = _buildTextTheme(colorScheme);

  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    colorScheme: colorScheme,
    scaffoldBackgroundColor: _Brand.background,
    canvasColor: _Brand.background,
    fontFamily: _fontFamily,
    textTheme: textTheme,
    splashFactory: InkSparkle.splashFactory,
    extensions: const <ThemeExtension<dynamic>>[AppTokens.standard],

    cardTheme: CardThemeData(
      color: _Brand.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.standard.lg),
      ),
    ),

    iconTheme: const IconThemeData(color: _Brand.text),

    iconButtonTheme: IconButtonThemeData(
      style: IconButton.styleFrom(
        backgroundColor: _Brand.muted,
        foregroundColor: _Brand.text,
        fixedSize: const Size.square(40),
        shape: const StadiumBorder(),
      ),
    ),

    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: _Brand.primary,
        foregroundColor: Colors.white,
        disabledBackgroundColor: _Brand.muted,
        disabledForegroundColor: _Brand.textDisabled,
        minimumSize: const Size(64, 44),
        padding: const EdgeInsets.symmetric(horizontal: 24),
        shape: const StadiumBorder(),
        textStyle: textTheme.titleSmall,
      ),
    ),

    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: _Brand.primaryDark,
        disabledForegroundColor: _Brand.textDisabled,
        side: const BorderSide(color: _Brand.primary, width: 1.5),
        minimumSize: const Size(64, 44),
        padding: const EdgeInsets.symmetric(horizontal: 20),
        shape: const StadiumBorder(),
        textStyle: textTheme.titleSmall,
      ),
    ),

    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: _Brand.primaryDark,
        disabledForegroundColor: _Brand.textDisabled,
        minimumSize: const Size(44, 44),
        padding: const EdgeInsets.symmetric(horizontal: 12),
        shape: const StadiumBorder(),
        textStyle: textTheme.titleSmall,
      ),
    ),

    segmentedButtonTheme: SegmentedButtonThemeData(
      style: ButtonStyle(
        shape: const WidgetStatePropertyAll<OutlinedBorder>(StadiumBorder()),
        side: const WidgetStatePropertyAll<BorderSide>(BorderSide.none),
        backgroundColor: WidgetStateProperty.resolveWith((
          Set<WidgetState> states,
        ) {
          return states.contains(WidgetState.selected)
              ? _Brand.surface
              : Colors.transparent;
        }),
        foregroundColor: WidgetStateProperty.resolveWith((
          Set<WidgetState> states,
        ) {
          return states.contains(WidgetState.selected)
              ? _Brand.primaryDark
              : _Brand.mutedForeground;
        }),
        textStyle: WidgetStatePropertyAll<TextStyle?>(
          textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w800),
        ),
      ),
    ),

    // The pill-chip variant of the missing Button primitive (AC-DS-05):
    // filter chips, dietary chips and similar toggleable pills use the
    // built-in `FilterChip`/`ChoiceChip` family themed to a stadium shape,
    // instead of a hand-rolled `Pressable` + `Container`.
    chipTheme: ChipThemeData(
      backgroundColor: _Brand.muted,
      selectedColor: _Brand.primaryLight,
      disabledColor: _Brand.muted,
      shape: const StadiumBorder(),
      side: BorderSide.none,
      showCheckmark: false,
      labelStyle: textTheme.labelLarge?.copyWith(
        color: _Brand.mutedForeground,
        fontWeight: FontWeight.w700,
      ),
      secondaryLabelStyle: textTheme.labelLarge?.copyWith(
        color: _Brand.primaryDark,
        fontWeight: FontWeight.w700,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
      labelPadding: EdgeInsets.zero,
    ),

    // Undo snackbar (AC-UX-02, AC-DS-10) — see `snackbar.dart` for the
    // `GleanSnackBar.showUndo` helper that rides on top of this theme.
    snackBarTheme: SnackBarThemeData(
      backgroundColor: _Brand.ink,
      contentTextStyle: textTheme.bodyMedium?.copyWith(color: Colors.white),
      actionTextColor: _Brand.primaryLight,
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.standard.md),
      ),
      insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
    ),

    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: _Brand.muted,
      hintStyle: textTheme.bodyLarge?.copyWith(color: _Brand.textDisabled),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.standard.md),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.standard.md),
        borderSide: BorderSide.none,
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.standard.md),
        borderSide: const BorderSide(color: _Brand.primary, width: 2),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadius.standard.md),
        borderSide: const BorderSide(color: _Brand.danger, width: 1.5),
      ),
    ),

    appBarTheme: AppBarTheme(
      backgroundColor: _Brand.background,
      foregroundColor: _Brand.text,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: textTheme.titleLarge,
      iconTheme: const IconThemeData(color: _Brand.text),
    ),

    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: _Brand.surface,
      surfaceTintColor: Colors.transparent,
      indicatorColor: _Brand.primaryLight,
      indicatorShape: const StadiumBorder(),
      height: 64,
      labelTextStyle: WidgetStateProperty.resolveWith((
        Set<WidgetState> states,
      ) {
        final bool selected = states.contains(WidgetState.selected);
        return (textTheme.labelSmall ?? const TextStyle()).copyWith(
          color: selected ? _Brand.primaryDark : _Brand.mutedForeground,
          fontWeight: FontWeight.w700,
        );
      }),
      iconTheme: WidgetStateProperty.resolveWith((Set<WidgetState> states) {
        final bool selected = states.contains(WidgetState.selected);
        return IconThemeData(
          color: selected ? _Brand.primaryDark : _Brand.mutedForeground,
        );
      }),
    ),

    // No `DismissThemeData`/`DismissibleThemeData` exists in the Flutter SDK
    // (verified against the vendored framework source at this Flutter
    // version) — `Dismissible` has no theme extension point to fill, so
    // there is nothing to set here; see `swipe_to_delete.dart` for the thin
    // themed wrapper instead (AC-DS-09).
    dividerTheme: const DividerThemeData(
      color: _Brand.border,
      space: 1,
      thickness: 1,
    ),
  );
}

/// Builds a full Material [TextTheme] off the RN `theme.typography` scale.
/// Every RN entry maps onto the nearest Material role by rendered size, with
/// the RN size/weight applied verbatim rather than the Material default:
///
/// | RN token       | size / weight | Material role  |
/// |-----------------|---------------|-----------------|
/// | `largeTitle`    | 30 / 800      | `headlineLarge` |
/// | `title2`        | 22 / 700      | `titleLarge`    |
/// | `headline`      | 17 / 700      | `titleMedium`   |
/// | `body`          | 16 / 400      | `bodyLarge`     |
/// | `subhead`       | 14 / 600      | `bodyMedium`    |
/// | `caption`       | 12 / 600      | `bodySmall`     |
/// | `sectionLabel`  | 12 / 800      | `labelSmall`    |
///
/// Roles the RN scale never defined (`displayLarge`/`Medium`/`Small`,
/// `headlineMedium`/`Small`, `titleSmall`, `labelLarge`/`Medium`) fall back to
/// Material's own scale with the brand family/colour applied, so nothing in
/// the theme is left un-branded even where RN had no equivalent.
///
/// Flutter's `TextStyle` has no `textTransform` — RN's `sectionLabel` relies
/// on `text-transform: uppercase` in the stylesheet, which has no direct
/// Flutter equivalent. Callers that need the RN look must call
/// `.toUpperCase()` on the string themselves; this is flagged in the final
/// report as a spec gap, not silently ported around.
TextTheme _buildTextTheme(ColorScheme colorScheme) {
  final TextTheme base =
      Typography.material2021(
        platform: TargetPlatform.iOS,
        colorScheme: colorScheme,
      ).black.apply(
        fontFamily: _fontFamily,
        displayColor: _Brand.text,
        bodyColor: _Brand.text,
      );

  return base.copyWith(
    headlineLarge: base.headlineLarge?.copyWith(
      fontSize: 30,
      fontWeight: FontWeight.w800,
      letterSpacing: -0.6,
      color: _Brand.text,
    ),
    titleLarge: base.titleLarge?.copyWith(
      fontSize: 22,
      fontWeight: FontWeight.w700,
      color: _Brand.text,
    ),
    titleMedium: base.titleMedium?.copyWith(
      fontSize: 17,
      fontWeight: FontWeight.w700,
      color: _Brand.text,
    ),
    bodyLarge: base.bodyLarge?.copyWith(
      fontSize: 16,
      fontWeight: FontWeight.w400,
      color: _Brand.text,
    ),
    bodyMedium: base.bodyMedium?.copyWith(
      fontSize: 14,
      fontWeight: FontWeight.w600,
      color: _Brand.textSecondary,
    ),
    bodySmall: base.bodySmall?.copyWith(
      fontSize: 12,
      fontWeight: FontWeight.w600,
      color: _Brand.textSecondary,
    ),
    labelSmall: base.labelSmall?.copyWith(
      fontSize: 12,
      fontWeight: FontWeight.w800,
      letterSpacing: 0.96,
      color: const Color(0xFF6D6A5C),
    ),
  );
}
