/// Shared startup wiring for both entrypoints.
///
/// `main.dart` and `main_e2e.dart` differ *only* in how they satisfy the auth
/// seams; everything else — config, the database gate, `runApp` — lives here so
/// the two cannot drift apart. Keeping the bypass out of this file is what lets
/// `main.dart`'s import graph stay free of it (AC-AUTH-06).
library;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'data/providers/database_providers.dart';
import 'design_system/design_system.dart';

/// Build-time configuration, supplied via `--dart-define`.
///
/// The RN app read these from `EXPO_PUBLIC_*` environment variables, which Expo
/// inlined at build time — the same mechanism, and the same caveat: these are
/// baked into the binary, so nothing secret belongs here. (A Cognito domain and
/// public client id are not secrets; a client *secret* would be, and the PKCE
/// flow deliberately has none.)
abstract final class GleanConfig {
  static const String apiBaseUrl = String.fromEnvironment('API_BASE_URL');
  static const String cognitoDomain = String.fromEnvironment('COGNITO_DOMAIN');
  static const String cognitoClientId = String.fromEnvironment(
    'COGNITO_CLIENT_ID',
  );

  /// Fails loudly at startup rather than surfacing later as a confusing
  /// "sign-in did nothing" or a request to `https:///oauth2/authorize`. The RN
  /// app defaulted these to `""` and carried on.
  static void assertComplete() {
    final missing = <String>[
      if (apiBaseUrl.isEmpty) 'API_BASE_URL',
      if (cognitoDomain.isEmpty) 'COGNITO_DOMAIN',
      if (cognitoClientId.isEmpty) 'COGNITO_CLIENT_ID',
    ];
    if (missing.isNotEmpty) {
      throw StateError(
        'Missing --dart-define values: ${missing.join(', ')}. '
        'Pass them at build/run time, e.g. '
        '--dart-define=API_BASE_URL=https://api.example.com',
      );
    }
  }
}

/// Shows the iOS status bar again once Flutter starts.
///
/// `flutter_native_splash.yaml`'s `fullscreen: true` hides the Android status
/// bar only on the launch theme, but on iOS it writes `UIStatusBarHidden` into
/// `Info.plist`, which keeps the bar hidden for the whole app. This is the fix
/// that package's README gives. Android is left alone so it keeps its default
/// system UI.
Future<void> showStatusBarAfterSplash() async {
  if (defaultTargetPlatform != TargetPlatform.iOS) return;
  await SystemChrome.setEnabledSystemUIMode(
    SystemUiMode.manual,
    overlays: SystemUiOverlay.values,
  );
}

/// Wraps [GleanApp] in the database gate.
///
/// The RN app caught its DB-init failure and ignored it, then proceeded with a
/// possibly-unusable database — so every subsequent read failed for
/// unexplained reasons. Here a failed open is shown to the user (AC-DATA-12).
class GleanRoot extends ConsumerWidget {
  const GleanRoot({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<void> ready = ref.watch(databaseReadyProvider);
    // R-09: the gate's three states used to swap via a bare `.when()` — a
    // hard cut reproducing the exact unanimated RN pop §7 calls out. Each
    // branch below is still its own full `MaterialApp` (no shared shell to
    // cross-fade a body under), so `GleanCrossFade` is used at the top —
    // its `skeleton` here is the pre-database-ready state, and `content`
    // covers ready-and-error (both post-decision terminal states; a switch
    // between them, if it ever happened, doesn't need this fade — that's
    // not the hand-off §7 is about).
    return GleanCrossFade(
      showSkeleton: ready.isLoading,
      skeleton: const _SplashHolding(),
      content: ready.when(
        data: (_) => const GleanApp(),
        loading: () => const _SplashHolding(),
        error: (Object error, StackTrace _) => _DatabaseErrorApp(error: error),
      ),
    );
  }
}

class _SplashHolding extends StatelessWidget {
  const _SplashHolding();

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: gleanLightTheme,
      home: const ColoredBox(color: Color(0xFF2E9D63)),
    );
  }
}

class _DatabaseErrorApp extends StatelessWidget {
  const _DatabaseErrorApp({required this.error});

  final Object error;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: gleanLightTheme,
      home: Scaffold(
        body: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Icon(
                Icons.error_outline_rounded,
                size: 48,
                color: Theme.of(context).colorScheme.error,
              ),
              const SizedBox(height: 16),
              Text(
                "Glean couldn't open its storage",
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text(
                'Your pantry, recipes and plan all live on this device, so the '
                'app cannot continue without them. Restarting usually fixes '
                'it; if it keeps happening, reinstalling will clear the '
                'damaged database.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 24),
              // Shown verbatim on purpose: this is unrecoverable in-app, so the
              // only useful thing left is something the user can report.
              Text(
                '$error',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
