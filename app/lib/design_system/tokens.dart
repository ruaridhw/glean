import 'package:flutter/material.dart';

/// Radius scale. `pill` is large-but-finite because [BorderRadius.circular] needs a finite radius; any
/// value at least half the shortest side renders as a full pill.
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

/// Spacing scale.
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

/// Elevation shadow presets. Each is a single [BoxShadow], which renders identically on both platforms.
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

/// The single [ThemeExtension] for brand tokens that don't fit `ColorScheme`/`TextTheme`. Everything else
/// is mapped onto `ColorScheme` in `theme.dart` so built-in widgets inherit the brand.
///
/// - `ink`: a dark neutral for a few inverted surfaces (checkout bar, selected filter chip, sign-in
///   background). The nearest `ColorScheme` slot, `inverseSurface`, is reserved for the `SnackBar` theme.
/// - `primaryLight`: a directly-named token rather than `colorScheme.primaryContainer`.
/// - `warning`/`success` (and their light variants): `ColorScheme` has no such roles. `danger` maps onto
///   `colorScheme.error`/`errorContainer` and is not duplicated here.
/// - `radius`/`spacing`/`shadow`: the scales themselves.
@immutable
class AppTokens extends ThemeExtension<AppTokens> {
  const AppTokens({
    required this.ink,
    required this.primaryLight,
    required this.warning,
    required this.warningLight,
    required this.success,
    required this.successLight,
    required this.onCamera,
    required this.cameraScrim,
    required this.cameraBackdrop,
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

  /// Over a live camera preview the brand palette is unreadable; these are the
  /// only non-brand colours and they stay tokens so a dark theme can retune them.
  final Color onCamera;
  final Color cameraScrim;
  final Color cameraBackdrop;
  final AppRadius radius;
  final AppSpacing spacing;
  final AppShadow shadow;

  /// The brand's one token set; there is no dark variant.
  static const AppTokens standard = AppTokens(
    ink: Color(0xFF26362B),
    primaryLight: Color(0xFFE3F2E7),
    warning: Color(0xFFA8631F),
    warningLight: Color(0xFFFBE9D6),
    success: Color(0xFF1C6B41),
    successLight: Color(0xFFE3F2E7),
    onCamera: Color(0xFFFFFFFF),
    cameraScrim: Color(0x73000000), // black at 45% alpha
    cameraBackdrop: Color(0xFF111511),
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
    Color? onCamera,
    Color? cameraScrim,
    Color? cameraBackdrop,
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
      onCamera: onCamera ?? this.onCamera,
      cameraScrim: cameraScrim ?? this.cameraScrim,
      cameraBackdrop: cameraBackdrop ?? this.cameraBackdrop,
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
      onCamera: Color.lerp(onCamera, other.onCamera, t)!,
      cameraScrim: Color.lerp(cameraScrim, other.cameraScrim, t)!,
      cameraBackdrop: Color.lerp(cameraBackdrop, other.cameraBackdrop, t)!,
      radius: t < 0.5 ? radius : other.radius,
      spacing: t < 0.5 ? spacing : other.spacing,
      shadow: t < 0.5 ? shadow : other.shadow,
    );
  }
}

/// Reaches [AppTokens] through `Theme.of(context)`, never a global const.
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
