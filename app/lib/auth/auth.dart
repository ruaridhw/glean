/// The Glean AUTH module. Feature/orchestrator code should import this
/// barrel rather than reaching into individual files — with one deliberate
/// exception: **`auth_bypass.dart` is never exported here.** `main.dart`
/// importing `package:glean/auth/auth.dart` must not be able to reach the
/// e2e bypass transitively (AC-AUTH-06) — only `main_e2e.dart` imports that
/// file directly, by its own explicit path.
///
/// Exports: [AuthController]/`authControllerProvider`, [CognitoAuthClient],
/// [SecureTokenStorage], the [AuthSession]/[resolveAuthSession] pure logic,
/// and `aiFeaturesAvailableProvider`.
library;

export 'auth_controller.dart';
export 'auth_mode.dart';
export 'cognito_auth_client.dart';
export 'token_storage.dart';
export 'tokens.dart';
