import 'dart:convert';

import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:glean/auth/app_auth_gateway.dart';
import 'package:glean/auth/cognito_auth_client.dart';
import 'package:glean/auth/token_storage.dart';
import 'package:glean/auth/tokens.dart';
import 'package:mocktail/mocktail.dart';

/// An in-memory [TokenStorage] fake — the direct analogue of
/// `test/data/fixture.dart`'s real in-memory database, but for secure
/// storage, which has no equivalent "real, but in-memory" test mode.
///
/// Exposes its state directly (rather than only via [readTokens]) so tests
/// can assert storage's *own* view of the world after a controller method
/// runs, proving `hasTokens`-style agreement (AC-AUTH-05) without going
/// through the controller a second time.
class InMemoryTokenStorage implements TokenStorage {
  String? accessToken;
  String? refreshToken;
  String? idToken;
  String? userSub;
  String? email;
  DateTime? expiresAt;

  int clearAllCalls = 0;
  int clearTokensKeepIdentityCalls = 0;
  int saveTokensCalls = 0;

  @override
  Future<StoredTokenValues> readTokens() async {
    return StoredTokenValues(
      accessToken: accessToken,
      refreshToken: refreshToken,
      idToken: idToken,
      userSub: userSub,
      email: email,
      expiresAt: expiresAt,
    );
  }

  @override
  Future<void> saveTokens(CognitoTokens tokens) async {
    saveTokensCalls += 1;
    accessToken = tokens.accessToken;
    refreshToken = tokens.refreshToken;
    idToken = tokens.idToken;
    userSub = tokens.userSub;
    email = tokens.email;
    expiresAt = tokens.expiresAt;
  }

  @override
  Future<void> clearAll() async {
    clearAllCalls += 1;
    accessToken = null;
    refreshToken = null;
    idToken = null;
    userSub = null;
    email = null;
    expiresAt = null;
  }

  @override
  Future<void> clearTokensKeepIdentity() async {
    clearTokensKeepIdentityCalls += 1;
    accessToken = null;
    refreshToken = null;
    idToken = null;
    expiresAt = null;
  }
}

/// Mocks the platform-channel seam `CognitoAuthClient` talks to
/// (`test/auth/cognito_auth_client_test.dart`).
class MockAppAuthGateway extends Mock implements AppAuthGateway {}

/// Mocks the network seam `AuthController` talks to
/// (`test/auth/auth_controller_test.dart`). `CognitoAuthClient` is a
/// concrete class, but mocktail's `Mock` intercepts every call via
/// `noSuchMethod` regardless of the real class having its own constructor
/// logic — nothing in `CognitoAuthClient`'s constructor runs.
class MockCognitoAuthClient extends Mock implements CognitoAuthClient {}

/// Registers the fallback values mocktail needs for `any()`/`captureAny()`
/// matchers against methods whose parameters aren't primitive types. Call
/// once from a `setUpAll` in any test file that mocks [AppAuthGateway].
void registerAuthFallbackValues() {
  registerFallbackValue(
    AuthorizationTokenRequest(
      'fallback-client-id',
      'glean://auth/callback',
      serviceConfiguration: const AuthorizationServiceConfiguration(
        authorizationEndpoint: 'https://example.com/oauth2/authorize',
        tokenEndpoint: 'https://example.com/oauth2/token',
      ),
    ),
  );
  registerFallbackValue(
    TokenRequest(
      'fallback-client-id',
      'glean://auth/callback',
      serviceConfiguration: const AuthorizationServiceConfiguration(
        authorizationEndpoint: 'https://example.com/oauth2/authorize',
        tokenEndpoint: 'https://example.com/oauth2/token',
      ),
      refreshToken: 'fallback-refresh-token',
      grantType: GrantType.refreshToken,
    ),
  );
}

/// Builds a minimal, syntactically-valid JWT (unsigned — nothing here
/// verifies a signature) carrying the given claims, for tests that exercise
/// [decodeJwtPayload]/[CognitoTokens.fromIdToken] without a real Cognito
/// response.
String buildTestJwt(Map<String, dynamic> claims) {
  String encodeSegment(Map<String, dynamic> value) =>
      base64Url.encode(utf8.encode(jsonEncode(value))).replaceAll('=', '');
  final String header = encodeSegment(const <String, dynamic>{
    'alg': 'none',
    'typ': 'JWT',
  });
  final String payload = encodeSegment(claims);
  return '$header.$payload.signature';
}
