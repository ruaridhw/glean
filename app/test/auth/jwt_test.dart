import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/jwt.dart';

import 'support/fakes.dart';

void main() {
  group('decodeJwtPayload', () {
    test('decodes the claims out of a well-formed JWT', () {
      final String jwt = buildTestJwt(const <String, dynamic>{
        'sub': 'user-sub-123',
        'email': 'test@gmail.com',
        'exp': 1700000000,
      });

      final Map<String, dynamic> claims = decodeJwtPayload(jwt);

      expect(claims['sub'], 'user-sub-123');
      expect(claims['email'], 'test@gmail.com');
      expect(claims['exp'], 1700000000);
    });

    test('throws for a token with no payload segment', () {
      expect(() => decodeJwtPayload('onlyoneSegment'), throwsFormatException);
      expect(() => decodeJwtPayload('header.'), throwsFormatException);
    });

    test('throws when the payload does not decode to a JSON object', () {
      final String header = buildTestJwt(
        const <String, dynamic>{},
      ).split('.')[0];
      // A JSON array, not an object, as the payload.
      final String arrayPayload = base64Url
          .encode(utf8.encode('[1,2,3]'))
          .replaceAll('=', '');
      expect(
        () => decodeJwtPayload('$header.$arrayPayload.sig'),
        throwsFormatException,
      );
    });
  });
}
