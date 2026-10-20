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
import 'logging/logging.dart';

/// Optional real tokens for a dedicated Cognito test user. All three or
/// none: with them the bypass session can call the local backend's AI
/// endpoints; without them it opens straight into the UI and cannot.
const String _e2eAccessToken = String.fromEnvironment('E2E_ACCESS_TOKEN');
const String _e2eIdToken = String.fromEnvironment('E2E_ID_TOKEN');
const String _e2eRefreshToken = String.fromEnvironment('E2E_REFRESH_TOKEN');

AuthSessionSnapshot _e2eSnapshot() {
  if (_e2eAccessToken.isEmpty &&
      _e2eIdToken.isEmpty &&
      _e2eRefreshToken.isEmpty) {
    return bypassAuthSnapshot();
  }
  if (_e2eAccessToken.isEmpty ||
      _e2eIdToken.isEmpty ||
      _e2eRefreshToken.isEmpty) {
    throw StateError(
      'E2E_ACCESS_TOKEN, E2E_ID_TOKEN and E2E_REFRESH_TOKEN must be passed '
      'together (scripts/e2e_tokens.sh issues all three).',
    );
  }
  return bypassAuthSnapshotWithTokens(
    CognitoTokens.fromIssuedTokens(
      accessToken: _e2eAccessToken,
      idToken: _e2eIdToken,
      refreshToken: _e2eRefreshToken,
    ),
  );
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final GleanLogger logger = await bootstrapLogging();
  await showStatusBarAfterSplash();
  GleanConfig.assertComplete();

  // Before installing any bypass override.
  assertAuthBypassUnreachable(GleanConfig.apiBaseUrl);

  final AuthSessionSnapshot snapshot = _e2eSnapshot();
  // Built exactly as main.dart builds them. Without injected tokens the
  // bypass snapshot carries none, so there is nothing to refresh and
  // `apiAccessTokenProvider` resolves to null: AI-backed calls fail at the
  // backend's auth check. With them, the client refreshes the test user's
  // session through the real Cognito domain exactly as production would.
  final TokenStorage storage = TokenStorage();
  final CognitoAuthClient client = CognitoAuthClient(
    cognitoDomain: GleanConfig.cognitoDomain,
    clientId: GleanConfig.cognitoClientId,
  );

  runApp(
    ProviderScope(
      overrides: [
        gleanLoggerProvider.overrideWithValue(logger),
        apiBaseUrlProvider.overrideWithValue(GleanConfig.apiBaseUrl),
        authControllerProvider.overrideWith(
          () => AuthController(snapshot, storage: storage, client: client),
        ),
      ],
      child: const GleanRoot(),
    ),
  );
}
