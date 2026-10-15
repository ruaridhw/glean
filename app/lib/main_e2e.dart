/// End-to-end test entrypoint — **never shipped**.
///
/// The auth bypass is a separate entrypoint rather than a flag, so it cannot
/// compile into a release binary at all: `main.dart` has no path to
/// `auth_bypass.dart`, and this file is the only importer of it.
/// [assertAuthBypassUnreachable] is the second line of defence, in case a build
/// script ever points this entrypoint at a production backend.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api/providers/api_providers.dart';
import 'auth/auth.dart';
import 'auth/auth_bypass.dart';
import 'bootstrap.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await showStatusBarAfterSplash();
  GleanConfig.assertComplete();

  // Before installing any bypass override.
  assertAuthBypassUnreachable(GleanConfig.apiBaseUrl);

  final AuthSessionSnapshot snapshot = bypassAuthSnapshot();
  // Built exactly as main.dart builds them. The bypass snapshot carries no
  // tokens, so there is nothing to refresh and `apiAccessTokenProvider`
  // resolves to null: AI-backed calls fail at the backend's auth check. That
  // is deliberate — an e2e build drives the UI, not production AI endpoints.
  final TokenStorage storage = TokenStorage();
  final CognitoAuthClient client = CognitoAuthClient(
    cognitoDomain: GleanConfig.cognitoDomain,
    clientId: GleanConfig.cognitoClientId,
  );

  runApp(
    ProviderScope(
      overrides: [
        apiBaseUrlProvider.overrideWithValue(GleanConfig.apiBaseUrl),
        authControllerProvider.overrideWith(
          () => AuthController(snapshot, storage: storage, client: client),
        ),
      ],
      child: const GleanRoot(),
    ),
  );
}
