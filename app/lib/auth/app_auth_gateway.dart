import 'package:flutter_appauth/flutter_appauth.dart';

/// Seam around `package:flutter_appauth`'s `FlutterAppAuth`, which is a
/// concrete class backed by a global platform-channel singleton
/// (`FlutterAppAuthPlatform.instance`) — there's no way to substitute its
/// behaviour in a test without this indirection, the same reason `Haptics`
/// wraps `HapticFeedback` rather than every caller touching it directly.
///
/// [CognitoAuthClient] depends on this, not on `FlutterAppAuth` — tests
/// mock this interface instead of a plugin platform channel.
abstract class AppAuthGateway {
  Future<AuthorizationTokenResponse> authorizeAndExchangeCode(
    AuthorizationTokenRequest request,
  );

  Future<TokenResponse> token(TokenRequest request);
}

/// The production [AppAuthGateway]: a thin pass-through to the real AppAuth
/// SDKs via `flutter_appauth`.
class SystemAppAuthGateway implements AppAuthGateway {
  const SystemAppAuthGateway();

  static const FlutterAppAuth _appAuth = FlutterAppAuth();

  @override
  Future<AuthorizationTokenResponse> authorizeAndExchangeCode(
    AuthorizationTokenRequest request,
  ) => _appAuth.authorizeAndExchangeCode(request);

  @override
  Future<TokenResponse> token(TokenRequest request) => _appAuth.token(request);
}
