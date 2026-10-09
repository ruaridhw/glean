import 'dart:convert';

import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:glean/auth/cognito_auth_client.dart';
import 'package:mocktail/mocktail.dart';

/// Mocks `flutter_appauth`'s platform-channel client, which
/// [CognitoAuthClient] takes as a constructor argument.
class MockFlutterAppAuth extends Mock implements FlutterAppAuth {}

/// Mocks the network seam `AuthController` talks to
/// (`test/auth/auth_controller_test.dart`). `CognitoAuthClient` is a
/// concrete class, but mocktail's `Mock` intercepts every call via
/// `noSuchMethod` regardless of the real class having its own constructor
/// logic — nothing in `CognitoAuthClient`'s constructor runs.
class MockCognitoAuthClient extends Mock implements CognitoAuthClient {}

/// Registers the fallback values mocktail needs for `any()`/`captureAny()`
/// matchers against methods whose parameters aren't primitive types. Call
/// once from a `setUpAll` in any test file that mocks [FlutterAppAuth].
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
