/// The Glean auth module. Other code imports this barrel rather than
/// reaching into individual files — with one deliberate exception:
/// **`auth_bypass.dart` is never exported here.** `main.dart` importing
/// `package:glean/auth/auth.dart` must not be able to reach the e2e bypass
/// transitively — only `main_e2e.dart` imports that file, by its own
/// explicit path.
///
/// Exports: [AuthController]/`authControllerProvider`,
/// `aiFeaturesAvailableProvider`, [CognitoAuthClient], [TokenStorage] and
/// [isProductionApiBaseUrl].
library;

export 'auth_controller.dart';
export 'auth_mode.dart';
export 'cognito_auth_client.dart';
export 'token_storage.dart';
export 'tokens.dart';
