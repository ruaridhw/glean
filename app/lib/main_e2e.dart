/// End-to-end test entrypoint — **never shipped**.
///
/// The RN app expressed this as `EXPO_PUBLIC_AUTH_BYPASS=true`, a compile-time
/// inlined flag that CI baked into a `gradlew assembleRelease` APK alongside the
/// production API URL. That was not exploitable (every backend LLM router
/// requires a valid token, so the build opened into the UI but could not call
/// any AI endpoint) — but nothing *structurally* stopped those variables being
/// set on a production profile.
///
/// Here the bypass is a separate entrypoint instead of a flag, so it cannot
/// compile into a release binary at all: `main.dart` has no path to
/// `auth_bypass.dart`, and this file is the only importer of it (AC-AUTH-06).
/// [assertAuthBypassUnreachable] is the second line of defence, in case a build
/// script ever points this entrypoint at a production backend.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod/misc.dart';

import 'api/providers/api_providers.dart';
import 'auth/auth.dart';
import 'auth/auth_bypass.dart';
import 'bootstrap.dart';
import 'data/providers/database_providers.dart';
import 'features/settings/providers/sign_out_action.dart';
import 'router/auth_state.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  GleanConfig.assertComplete();

  // Before installing any bypass override.
  assertAuthBypassUnreachable(GleanConfig.apiBaseUrl);

  final AuthSessionSnapshot snapshot = bypassAuthSnapshot();

  runApp(
    ProviderScope(
      overrides: <Override>[
        apiBaseUrlProvider.overrideWithValue(GleanConfig.apiBaseUrl),
        // No storage and no client: the bypass snapshot carries no tokens, so
        // `apiAccessTokenProvider` resolves to null and AI-backed calls fail
        // at the backend's auth check. That is deliberate — an e2e build drives
        // the UI, it does not exercise production AI endpoints.
        authControllerProvider.overrideWith(
          () => AuthController.seeded(snapshot),
        ),
        authStatusProvider.overrideWith(
          () => SeededAuthStatusNotifier(snapshot.status),
        ),
        currentUserIdProvider.overrideWith((Ref ref) {
          final String? userId = ref.watch(authControllerProvider).userId;
          if (userId == null) {
            throw StateError('bypass snapshot resolved no user id');
          }
          return userId;
        }),
        apiAccessTokenProvider.overrideWith(
          (Ref ref) =>
              ref.watch(authControllerProvider.notifier).getValidAccessToken,
        ),
        signOutActionProvider.overrideWith(
          (Ref ref) => ref.watch(authControllerProvider.notifier).signOut,
        ),
      ],
      child: const GleanRoot(),
    ),
  );
}
