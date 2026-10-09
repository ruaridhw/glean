import 'jwt.dart';

/// A complete, usable Cognito token set: what [AuthController] holds while a
/// session is `active`, and what [TokenStorage] persists.
class CognitoTokens {
  const CognitoTokens({
    required this.accessToken,
    required this.refreshToken,
    required this.idToken,
    required this.userSub,
    required this.email,
    required this.expiresAt,
  });

  final String accessToken;
  final String refreshToken;
  final String idToken;

  /// The stable Cognito subject — `currentUserIdProvider`'s value, never an
  /// email or display name that can change.
  final String userSub;
  final String email;
  final DateTime expiresAt;

  /// A 30s safety margin so a token already expired by the time a request
  /// actually reaches the server is treated as expired *now*, not "still
  /// good enough".
  bool get isExpired =>
      !DateTime.now().isBefore(expiresAt.subtract(const Duration(seconds: 30)));

  /// Builds tokens from a fresh Cognito response, decoding `sub`/`email` out
  /// of the ID token's JWT payload — Cognito's token responses don't return
  /// them as separate fields (mirrors the Expo app's `src/auth/google.ts`'s
  /// `decodeIdTokenPayload`, see git history).
  ///
  /// Throws [FormatException] if the ID token has no usable `sub` claim —
  /// [CognitoAuthClient] treats that identically to a missing token
  /// altogether, never returning tokens it can't attach a stable user id to.
  factory CognitoTokens.fromIdToken({
    required String accessToken,
    required String idToken,
    required String refreshToken,
    required DateTime expiresAt,
  }) {
    final Map<String, dynamic> claims = decodeJwtPayload(idToken);
    final Object? sub = claims['sub'];
    if (sub is! String || sub.isEmpty) {
      throw const FormatException('ID token is missing a "sub" claim.');
    }
    final Object? email = claims['email'];
    return CognitoTokens(
      accessToken: accessToken,
      refreshToken: refreshToken,
      idToken: idToken,
      userSub: sub,
      email: email is String ? email : '',
      expiresAt: expiresAt,
    );
  }
}
