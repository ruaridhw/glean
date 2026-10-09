/// Shared startup wiring for both entrypoints, which differ only in how they satisfy the auth seams.
/// Keeping the bypass out of this file keeps `main.dart`'s import graph free of it.
library;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'data/providers/database_providers.dart';
import 'design_system/design_system.dart';

/// Build-time configuration, supplied via `--dart-define`. Baked into the binary, so nothing secret
/// belongs here (the PKCE flow has no client secret).
abstract final class GleanConfig {
  static const String apiBaseUrl = String.fromEnvironment('API_BASE_URL');
  static const String cognitoDomain = String.fromEnvironment('COGNITO_DOMAIN');
  static const String cognitoClientId = String.fromEnvironment(
    'COGNITO_CLIENT_ID',
  );

  /// Fails loudly at startup rather than surfacing later as a confusing sign-in failure.
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

/// Wraps [GleanApp] in the database gate. A failed open is shown to the user rather than proceeding
/// with an unusable database.
class GleanRoot extends ConsumerWidget {
  const GleanRoot({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<void> ready = ref.watch(databaseReadyProvider);
    // Each branch is its own full `MaterialApp`, so the splash cross-fades
    // into whichever terminal state (app or error) the gate resolves to.
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 220),
      child: KeyedSubtree(
        key: ValueKey<bool>(ready.isLoading),
        child: ready.when(
          data: (_) => const GleanApp(),
          loading: () => const _SplashHolding(),
          error: (Object error, StackTrace _) =>
              _DatabaseErrorApp(error: error),
        ),
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
      home: Builder(
        builder: (BuildContext context) =>
            ColoredBox(color: Theme.of(context).colorScheme.primary),
      ),
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
        body: Builder(
          builder: (BuildContext context) => Padding(
            padding: EdgeInsets.all(context.tokens.spacing.xl),
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
      ),
    );
  }
}
