import 'package:flutter/widgets.dart';
import 'package:flutter_svg/flutter_svg.dart';

import 'tokens.dart';

/// Which vendored brand SVG to render.
///
/// The vendored SVGs live under `app/assets/brand/`.
enum GleanMarkAsset {
  /// `glean-b1-icon.svg` — the app icon glyph, square-ish, for small chrome
  /// (headers, sign-in).
  icon,

  /// `glean-b1-splash-logo.svg` — the wordmark/lockup used on the splash
  /// screen composition (`flutter_native_splash.yaml`).
  splashLogo,

  /// `glean-b1-adaptive-foreground.svg` — the Android adaptive-icon foreground layer; consumed by the
  /// launcher-icon pipeline, not drawn by app UI.
  adaptiveForeground,
}

const Map<GleanMarkAsset, String> _assetPaths = <GleanMarkAsset, String>{
  GleanMarkAsset.icon: 'assets/brand/glean-b1-icon.svg',
  GleanMarkAsset.splashLogo: 'assets/brand/glean-b1-splash-logo.svg',
  GleanMarkAsset.adaptiveForeground:
      'assets/brand/glean-b1-adaptive-foreground.svg',
};

/// Renders the Glean brand mark from a vendored SVG via `flutter_svg`. The SVGs carry no drop shadow
/// (`flutter_svg` cannot render `feDropShadow`), so the shadow is applied here from the theme's `card` token.
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
