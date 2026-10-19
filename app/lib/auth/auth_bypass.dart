/// **E2E-ONLY.** Backs `main_e2e.dart`'s fake auth session.
///
/// Never import this from `main.dart` or anything it imports: that keeps the bypass structurally
/// unreachable from a production binary. The `auth.dart` barrel does not export it, and
/// `test/standards/house_rules_test.dart` fails if anything besides `lib/main_e2e.dart` imports it.
library;

import 'auth_status.dart';
import 'auth_controller.dart';
import 'auth_mode.dart';
import 'tokens.dart';

/// The identity `main_e2e.dart` signs in as unless it supplies its own.
const String kAuthBypassUserSub = 'e2e-bypass-user-sub';

/// The always-active snapshot `main_e2e.dart` seeds [AuthController] with.
/// It carries no tokens at all, so `apiAccessTokenProvider` always resolves
/// to `null`. That's deliberate, not a gap: every backend LLM router requires
/// a valid token, so a bypass build opens straight into the UI but cannot
/// call a real AI endpoint.
AuthSessionSnapshot bypassAuthSnapshot({String userId = kAuthBypassUserSub}) =>
    AuthSessionSnapshot(status: AuthStatus.active, userId: userId);

/// A bypass session that *does* carry tokens: those of a dedicated Cognito
/// test user, issued by a script (`scripts/e2e_tokens.sh`) and handed to
/// `main_e2e.dart` as `--dart-define=E2E_*_TOKEN=...`. Lets a web dev loop or
/// an e2e run reach the AI-backed flows against a local backend, which
/// verifies them against the real pool's public keys. The identity is the
/// token's `sub`, so on-device data lands under the test user, not the
/// placeholder.
AuthSessionSnapshot bypassAuthSnapshotWithTokens(CognitoTokens tokens) =>
    AuthSessionSnapshot(
      status: AuthStatus.active,
      userId: tokens.userSub,
      tokens: tokens,
    );

/// `main_e2e.dart` must call this, with the same API base URL it's about to
/// configure `apiBaseUrlProvider` with, before installing any bypass
/// override. Throws if [apiBaseUrl] looks like a production backend —
/// defence-in-depth on top of the bypass already being unreachable from
/// `main.dart`'s import graph, in case a build script ever points the e2e
/// entrypoint at the wrong URL.
void assertAuthBypassUnreachable(String apiBaseUrl) {
  if (isProductionApiBaseUrl(apiBaseUrl)) {
    throw StateError(
      'Refusing to start the e2e entrypoint against what looks like a '
      'production API base URL ($apiBaseUrl). main_e2e.dart is for '
      'local/CI test backends only.',
    );
  }
}
