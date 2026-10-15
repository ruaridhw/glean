/// Production entrypoint.
///
/// This file must never be able to reach `lib/auth/auth_bypass.dart`, even
/// transitively — that is what makes the e2e auth bypass impossible to compile
/// into a release binary rather than merely disabled by a flag.
/// `package:glean/auth/auth.dart` deliberately does not export it, and
/// `test/standards/house_rules_test.dart` scans `lib/` to keep it that way.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api/providers/api_providers.dart';
import 'auth/auth.dart';
import 'bootstrap.dart';
import 'logging/logging.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final GleanLogger logger = await bootstrapLogging();
  await showStatusBarAfterSplash();
  GleanConfig.assertComplete();

  final TokenStorage storage = TokenStorage();
  final CognitoAuthClient client = CognitoAuthClient(
    cognitoDomain: GleanConfig.cognitoDomain,
    clientId: GleanConfig.cognitoClientId,
  );

  // Read secure storage *before* runApp. `currentUserIdProvider` is a plain
  // synchronous Provider that every repository depends on, so it must already
  // be correct on its first read — there is no "still checking" state for it to
  // occupy. Paying one async read here removes that whole class of problem.
  final AuthSessionSnapshot snapshot = await loadInitialAuthSnapshot(storage);

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
