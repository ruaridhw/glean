/// Opens an external URL, via `url_launcher`.
///
/// A DI seam — mirrors [hapticsProvider]/`signOutActionProvider` — so a
/// widget test can assert *which* URL a tap tried to open without touching
/// a real platform channel: `url_launcher` has none registered under plain
/// `flutter test`, so calling it directly from a test would throw
/// `MissingPluginException` rather than merely failing to open a browser.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart' as url_launcher;

/// Returns whether the URL was actually launched (mirrors
/// `url_launcher`'s own `launchUrl` return value).
typedef LinkOpener = Future<bool> Function(Uri uri);

final Provider<LinkOpener> linkOpenerProvider = Provider<LinkOpener>((Ref ref) {
  return (Uri uri) => url_launcher.launchUrl(
    uri,
    mode: url_launcher.LaunchMode.externalApplication,
  );
});
