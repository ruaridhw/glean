import 'dart:convert';

/// Decodes a JWT's payload (the middle, base64url-encoded segment) into a
/// JSON map — the Flutter port of `mobile/src/auth/google.ts`'s
/// `decodeIdTokenPayload`. Unlike the RN version, there is no need to
/// translate the base64url alphabet (`-`/`_`) to standard base64 (`+`/`/`)
/// first: `dart:convert`'s [base64Url] codec already understands it
/// natively, and [base64Url.normalize] restores the padding JWTs omit.
///
/// Throws [FormatException] for anything that isn't a well-formed JWT with a
/// JSON object payload — callers decide how to react (AUTH treats it as an
/// unusable token, never as a session it can trust).
Map<String, dynamic> decodeJwtPayload(String jwt) {
  final List<String> segments = jwt.split('.');
  if (segments.length < 2 || segments[1].isEmpty) {
    throw const FormatException('Invalid JWT: missing payload segment.');
  }

  final String normalized = base64Url.normalize(segments[1]);
  final dynamic decoded = jsonDecode(utf8.decode(base64Url.decode(normalized)));
  if (decoded is! Map<String, dynamic>) {
    throw const FormatException('Invalid JWT: payload is not a JSON object.');
  }
  return decoded;
}
