import 'package:flutter_appauth/flutter_appauth.dart';

import 'tokens.dart';

/// A sign-in failure with a message safe to show a user. [cancelled]
/// distinguishes "the user closed the browser" (not worth interrupting them
/// over) from a real failure worth a snackbar — see `SignInScreen`.
class AuthException implements Exception {
  const AuthException(this.message, {this.cancelled = false});

  final String message;
  final bool cancelled;

  @override
  String toString() => 'AuthException: $message';
}

/// Cognito Hosted UI -> Google, PKCE, via `flutter_appauth`.
///
/// Owns no session *state* (that's [AuthController]'s job) — just the two
/// network operations: exchange an authorization for tokens, and exchange a
/// refresh token for new ones. Never touches [TokenStorage] either; it hands
/// back [CognitoTokens] or `null`/an exception and lets the caller decide
/// what to persist.
class CognitoAuthClient {
  CognitoAuthClient({
    required String cognitoDomain,
    required this.clientId,
    this._appAuth = const FlutterAppAuth(),
  }) : _config = AuthorizationServiceConfiguration(
         authorizationEndpoint: 'https://$cognitoDomain/oauth2/authorize',
         tokenEndpoint: 'https://$cognitoDomain/oauth2/token',
       );

  /// Must equal what `backend/template.yaml`'s Cognito app client declares
  /// as a `CallbackURL`, and what the native custom-scheme intent filter on
  /// each platform hands back to AppAuth.
  static const String redirectUri = 'glean://auth/callback';

  final String clientId;
  final AuthorizationServiceConfiguration _config;
  final FlutterAppAuth _appAuth;

  /// Opens Cognito Hosted UI -> Google and exchanges the returned
  /// authorization code for tokens in one native round trip.
  ///
  /// Consumes [FlutterAppAuth.authorizeAndExchangeCode]'s **return value**
  /// directly: that call blocks until the native
  /// `ASWebAuthenticationSession`/Custom Tab round trip (including the code
  /// exchange) is complete, so there is no separate deep-link listener that
  /// could miss the redirect and dead-end silently.
  Future<CognitoTokens> signIn() async {
    AuthorizationTokenResponse response;
    try {
      response = await _appAuth.authorizeAndExchangeCode(
        AuthorizationTokenRequest(
          clientId,
          redirectUri,
          serviceConfiguration: _config,
          scopes: const <String>['openid', 'email', 'profile'],
          // Google-only sign-in: sends the Hosted UI straight to the Google
          // federation rather than showing Cognito's provider picker.
          additionalParameters: const <String, String>{
            'identity_provider': 'Google',
          },
        ),
      );
    } on FlutterAppAuthUserCancelledException {
      throw const AuthException('Sign-in was cancelled.', cancelled: true);
    } catch (error) {
      throw AuthException('Sign-in failed: $error');
    }

    final String? accessToken = response.accessToken;
    final String? idToken = response.idToken;
    final String? refreshToken = response.refreshToken;
    if (accessToken == null ||
        accessToken.isEmpty ||
        idToken == null ||
        refreshToken == null ||
        refreshToken.isEmpty) {
      throw const AuthException(
        'Sign-in did not return a complete set of tokens.',
      );
    }

    try {
      return CognitoTokens.fromIdToken(
        accessToken: accessToken,
        idToken: idToken,
        refreshToken: refreshToken,
        expiresAt: response.accessTokenExpirationDateTime ?? DateTime.now(),
      );
    } on FormatException catch (error) {
      throw AuthException('Sign-in failed: $error');
    }
  }

  /// Exchanges [refreshToken] for a new access/id token pair.
  ///
  /// Returns `null` on **any** failure — a thrown platform/network error, or
  /// a 200 response missing a usable access or id token — rather than
  /// throwing, so [AuthController] has one uniform "treat this refresh as
  /// failed" signal. A structurally successful response with an empty access
  /// token is treated exactly like a network failure: never returned, so a
  /// caller can never persist it and keep reporting a valid session.
  Future<CognitoTokens?> refresh(String refreshToken) async {
    TokenResponse response;
    try {
      response = await _appAuth.token(
        TokenRequest(
          clientId,
          redirectUri,
          serviceConfiguration: _config,
          refreshToken: refreshToken,
          grantType: GrantType.refreshToken,
        ),
      );
    } catch (_) {
      return null;
    }

    final String? accessToken = response.accessToken;
    final String? idToken = response.idToken;
    if (accessToken == null ||
        accessToken.isEmpty ||
        idToken == null ||
        idToken.isEmpty) {
      return null;
    }

    try {
      return CognitoTokens.fromIdToken(
        accessToken: accessToken,
        idToken: idToken,
        // Cognito's refresh grant does not reissue a refresh token; keep
        // using the one the caller supplied.
        refreshToken: response.refreshToken ?? refreshToken,
        expiresAt: response.accessTokenExpirationDateTime ?? DateTime.now(),
      );
    } on FormatException {
      return null;
    }
  }
}
