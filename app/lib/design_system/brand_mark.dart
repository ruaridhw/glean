import 'package:flutter/widgets.dart';
import 'package:flutter_svg/flutter_svg.dart';

import 'tokens.dart';

/// Which vendored brand SVG to render.
///
/// FLUTTER_MIGRATION.md §2 calls this asset `assets/source/glean-mark.svg`.
/// That file does not exist in the repo — the real vendored SVGs under
/// `app/assets/brand/` are the three below. This is flagged as a spec/reality
/// discrepancy in the implementation report rather than silently invented.
enum GleanMarkAsset {
  /// `glean-b1-icon.svg` — the app icon glyph, square-ish, for small chrome
  /// (headers, sign-in).
  icon,

  /// `glean-b1-splash-logo.svg` — the wordmark/lockup used on the splash
  /// screen composition (`flutter_native_splash.yaml`).
  splashLogo,

  /// `glean-b1-adaptive-foreground.svg` — the Android adaptive-icon
  /// foreground layer. Included for completeness; not expected to be drawn
  /// by app UI (it's consumed by the platform launcher-icon pipeline), but
  /// kept alongside its siblings so all three vendored brand assets are
  /// reachable through one enum.
  adaptiveForeground,
}

const Map<GleanMarkAsset, String> _assetPaths = <GleanMarkAsset, String>{
  GleanMarkAsset.icon: 'assets/brand/glean-b1-icon.svg',
  GleanMarkAsset.splashLogo: 'assets/brand/glean-b1-splash-logo.svg',
  GleanMarkAsset.adaptiveForeground:
      'assets/brand/glean-b1-adaptive-foreground.svg',
};

/// Renders the Glean brand mark from a vendored SVG via `flutter_svg`
/// (AC-DS-07). Defaults to [GleanMarkAsset.icon].
///
/// F-01: the vendored SVGs used to bake a drop shadow into an
/// `feDropShadow` `<filter>`, which `flutter_svg` 2.3.0 cannot render — it
/// logged `unhandled element <filter/>` and silently dropped the shadow
/// (a silent visual regression against the RN app, plus console noise on
/// every test that touched sign-in or onboarding). The `<filter>` is now
/// stripped from the SVG source, and the same soft elevation shadow is
/// reapplied here instead, via the design system's own `card` shadow token
/// rather than a hand-rolled `BoxShadow` (AC-DS-03) — so every rendering of
/// the mark keeps its shadow, and it stays in sync if that token ever
/// changes per theme.
class GleanMark extends StatelessWidget {
  const GleanMark({super.key, this.asset = GleanMarkAsset.icon, this.size});

  final GleanMarkAsset asset;

  /// Applied to both width and height. `null` lets the SVG report its own
  /// intrinsic size.
  final double? size;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        boxShadow: <BoxShadow>[context.tokens.shadow.card],
      ),
      child: SvgPicture.asset(_assetPaths[asset]!, width: size, height: size),
    );
  }
}
