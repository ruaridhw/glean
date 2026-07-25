/// **E2E-ONLY.** This file backs `main_e2e.dart`'s fake auth session
/// (FLUTTER_MIGRATION.md §5, AC-AUTH-06).
///
/// It must **never** be imported by `main.dart` or anything `main.dart`
/// transitively imports — that's what makes the bypass structurally
/// unreachable from a production binary, rather than a flag someone could
/// flip on a production build (§5: "the bypass lives in a separate
/// `main_e2e.dart` entrypoint so the bypass path cannot compile into a
/// production binary at all"). `lib/auth/auth.dart` (the barrel every other
/// file should import) deliberately does **not** export this file, and
/// `test/auth/auth_bypass_test.dart` scans every `.dart` file under `lib/`
/// to prove nothing outside this file and `lib/main_e2e.dart` references it
/// by path — a CI grep can run the same check.
///
/// Everything here is otherwise ordinary, safe code — the isolation is
/// structural (which files import this one), not a property of what this
/// file's contents happen to do today.
library;

import '../router/auth_state.dart';
import 'auth_controller.dart';
import 'auth_mode.dart';

/// The identity `main_e2e.dart` uses unless it supplies its own (e.g. via
/// `--dart-define=E2E_BYPASS_USER_SUB=...`, mirroring mobile's
/// `EXPO_PUBLIC_AUTH_BYPASS_USER_SUB`).
const String kE2eBypassUserId = kAuthBypassUserSub;

/// The always-active, always-resolves-a-user snapshot `main_e2e.dart` seeds
/// [AuthController.seeded] and [SeededAuthStatusNotifier] with — no secure
/// storage, no network, and (per [resolveAuthSession]'s bypass branch) no
/// tokens at all, so `apiAccessTokenProvider`'s override built on top of
/// this always resolves to `null`. That's deliberate, not a gap: every
/// backend LLM router requires a valid token, so a bypass build opens
/// straight into the UI but cannot call a production AI endpoint (§5).
AuthSessionSnapshot bypassAuthSnapshot({String userId = kE2eBypassUserId}) {
  final AuthSession resolved = resolveAuthSession(
    stored: const StoredAuthValues(),
    bypassUserId: userId,
  );
  return AuthSessionSnapshot(
    status: AuthStatus.active,
    userId: resolved.userSub,
  );
}

/// AC-AUTH-06's startup assertion: `main_e2e.dart` must call this, with the
/// same API base URL it's about to configure `apiBaseUrlProvider` with,
/// before installing any bypass override. Throws if [apiBaseUrl] looks like
/// a production backend — defence-in-depth on top of the bypass already
/// being unreachable from `main.dart`'s import graph, in case a future
/// build script ever points the e2e entrypoint at the wrong URL.
void assertAuthBypassUnreachable(String apiBaseUrl) {
  if (isProductionApiBaseUrl(apiBaseUrl)) {
    throw StateError(
      'Refusing to start the e2e entrypoint against what looks like a '
      'production API base URL ($apiBaseUrl). main_e2e.dart is for '
      'local/CI test backends only.',
    );
  }
}
