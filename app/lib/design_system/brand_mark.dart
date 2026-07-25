import 'package:flutter/widgets.dart';
import 'package:flutter_svg/flutter_svg.dart';

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
class GleanMark extends StatelessWidget {
  const GleanMark({super.key, this.asset = GleanMarkAsset.icon, this.size});

  final GleanMarkAsset asset;

  /// Applied to both width and height. `null` lets the SVG report its own
  /// intrinsic size.
  final double? size;

  @override
  Widget build(BuildContext context) {
    return SvgPicture.asset(_assetPaths[asset]!, width: size, height: size);
  }
}
