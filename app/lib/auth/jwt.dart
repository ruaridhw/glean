import 'dart:convert';

/// Decodes a JWT's payload segment into a JSON map. Throws [FormatException] for anything that isn't a
/// well-formed JWT with a JSON object payload; callers treat that as an unusable token.
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
