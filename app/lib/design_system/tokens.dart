import 'package:flutter/material.dart';

/// Radius scale, ported 1:1 from the Expo app's `src/theme/index.ts`
/// (`theme.radius`; see git history).
///
/// `pill` uses a large-but-finite value (not `double.infinity`) because it
/// feeds [BorderRadius.circular], which requires a finite radius; any value
/// at least half the shortest side renders as a full stadium/pill, same as
/// React Native's `999`.
@immutable
class AppRadius {
  const AppRadius({
    required this.sm,
    required this.md,
    required this.lg,
    required this.xl,
    required this.pill,
  });

  final double sm;
  final double md;
  final double lg;
  final double xl;
  final double pill;

  static const AppRadius standard = AppRadius(
    sm: 8,
    md: 14,
    lg: 16,
    xl: 20,
    pill: 999,
  );
}

/// Spacing scale, ported 1:1 from the Expo app's `src/theme/index.ts`
/// (`theme.spacing`; see git history).
@immutable
class AppSpacing {
  const AppSpacing({
    required this.xs,
    required this.sm,
    required this.md,
    required this.lg,
    required this.xl,
    required this.xxl,
  });

  final double xs;
  final double sm;
  final double md;
  final double lg;
  final double xl;
  final double xxl;

  static const AppSpacing standard = AppSpacing(
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 24,
    xxl: 32,
  );
}

/// Elevation shadow presets, ported from the Expo app's `src/theme/index.ts`
/// (`theme.shadow`; see git history).
///
/// RN expressed these as `{shadowColor, shadowOffset, shadowOpacity, shadowRadius,
/// elevation}` for `Platform`-conditional rendering. Flutter has one shadow model
/// ([BoxShadow]) that works identically on both platforms, so each preset collapses
/// to a single [BoxShadow] rather than needing an elevation fallback.
@immutable
class AppShadow {
  const AppShadow({required this.card, required this.sheet, required this.fab});

  final BoxShadow card;
  final BoxShadow sheet;
  final BoxShadow fab;

  static const AppShadow standard = AppShadow(
    card: BoxShadow(
      color: Color(0x0F26362B), // #26362b at ~6% opacity
      offset: Offset(0, 2),
      blurRadius: 10,
    ),
    sheet: BoxShadow(
      color: Color(0x1A26362B), // #26362b at ~10% opacity
      offset: Offset(0, -2),
      blurRadius: 20,
    ),
    fab: BoxShadow(
      color: Color(0x4D2E9D63), // brand green at ~30% opacity
      offset: Offset(0, 4),
      blurRadius: 12,
    ),
  );
}

/// The single [ThemeExtension] for brand tokens that don't fit `ColorScheme`/
/// `TextTheme` (FLUTTER_MIGRATION.md §4, AC-DS-02). Everything else — the
/// primary/error/surface family — is mapped onto `ColorScheme` in `theme.dart`
/// so built-in widgets inherit the brand automatically.
///
/// What lives here and why:
/// - `ink`: a dark neutral used for a handful of *inverted* surfaces (the
///   checkout bar, the selected filter chip, the sign-in background). It has
///   no `ColorScheme` role of its own — closest is `inverseSurface`, but that
///   slot is reserved for `SnackBar`'s theme below, so it stays a plain token.
/// - `primaryLight`: kept as a directly-named token (not just read back off
///   `colorScheme.primaryContainer`) because call sites porting from
///   `theme.colors.primaryLight` should find an obviously-corresponding name.
/// - `warning`/`warningLight`, `success`/`successLight`: Material's
///   `ColorScheme` has no "warning" or "success" role, only `error`. `danger`/
///   `dangerLight` from the RN theme *does* have a natural home — it maps onto
///   `colorScheme.error`/`errorContainer` and is deliberately not duplicated
///   here (see `theme.dart`).
/// - `radius`/`spacing`/`shadow`: the scales themselves, unchanged from RN.
@immutable
class AppTokens extends ThemeExtension<AppTokens> {
  const AppTokens({
    required this.ink,
    required this.primaryLight,
    required this.warning,
    required this.warningLight,
    required this.success,
    required this.successLight,
    required this.radius,
    required this.spacing,
    required this.shadow,
  });

  final Color ink;
  final Color primaryLight;
  final Color warning;
  final Color warningLight;
  final Color success;
  final Color successLight;
  final AppRadius radius;
  final AppSpacing spacing;
  final AppShadow shadow;

  /// The brand's one and only token set today (no dark variant exists yet —
  /// FLUTTER_MIGRATION.md §1 rules dark mode out of scope for this port).
  static const AppTokens standard = AppTokens(
    ink: Color(0xFF26362B),
    primaryLight: Color(0xFFE3F2E7),
    warning: Color(0xFFA8631F),
    warningLight: Color(0xFFFBE9D6),
    success: Color(0xFF1C6B41),
    successLight: Color(0xFFE3F2E7),
    radius: AppRadius.standard,
    spacing: AppSpacing.standard,
    shadow: AppShadow.standard,
  );

  @override
  AppTokens copyWith({
    Color? ink,
    Color? primaryLight,
    Color? warning,
    Color? warningLight,
    Color? success,
    Color? successLight,
    AppRadius? radius,
    AppSpacing? spacing,
    AppShadow? shadow,
  }) {
    return AppTokens(
      ink: ink ?? this.ink,
      primaryLight: primaryLight ?? this.primaryLight,
      warning: warning ?? this.warning,
      warningLight: warningLight ?? this.warningLight,
      success: success ?? this.success,
      successLight: successLight ?? this.successLight,
      radius: radius ?? this.radius,
      spacing: spacing ?? this.spacing,
      shadow: shadow ?? this.shadow,
    );
  }

  @override
  AppTokens lerp(ThemeExtension<AppTokens>? other, double t) {
    if (other is! AppTokens) {
      return this;
    }
    // Only colours are meaningfully interpolated; the structural scales
    // (radius/spacing/shadow) are identical across the only theme that exists
    // today, so a hard switch at the midpoint is correct and keeps this
    // trivial to extend once a second (dark) ThemeData exists.
    return AppTokens(
      ink: Color.lerp(ink, other.ink, t)!,
      primaryLight: Color.lerp(primaryLight, other.primaryLight, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      warningLight: Color.lerp(warningLight, other.warningLight, t)!,
      success: Color.lerp(success, other.success, t)!,
      successLight: Color.lerp(successLight, other.successLight, t)!,
      radius: t < 0.5 ? radius : other.radius,
      spacing: t < 0.5 ? spacing : other.spacing,
      shadow: t < 0.5 ? shadow : other.shadow,
    );
  }
}

/// Reaches [AppTokens] through `Theme.of(context)` — never a global const at
/// the call site (AC-DS-03). This is what keeps a future dark theme a second
/// `ThemeData` instead of a codebase-wide refactor.
extension AppTokensX on BuildContext {
  AppTokens get tokens {
    final AppTokens? extension = Theme.of(this).extension<AppTokens>();
    assert(
      extension != null,
      'gleanLightTheme must register an AppTokens ThemeExtension.',
    );
    return extension ?? AppTokens.standard;
  }
}
