import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/tokens.dart';

import 'support/fakes.dart';

void main() {
  group('CognitoTokens.fromIssuedTokens', () {
    final int exp = DateTime.utc(2030, 1, 1).millisecondsSinceEpoch ~/ 1000;
    final String access = buildTestJwt({'sub': 'user-1', 'exp': exp});
    final String id = buildTestJwt({'sub': 'user-1', 'email': 'a@b.c'});

    test('takes the expiry from the access token and identity from the id '
        'token', () {
      final CognitoTokens tokens = CognitoTokens.fromIssuedTokens(
        accessToken: access,
        idToken: id,
        refreshToken: 'refresh',
      );
      expect(tokens.expiresAt, DateTime.utc(2030, 1, 1));
      expect(tokens.userSub, 'user-1');
      expect(tokens.email, 'a@b.c');
      expect(tokens.refreshToken, 'refresh');
      expect(tokens.isExpired, isFalse);
    });

    test('rejects an access token without a numeric exp', () {
      expect(
        () => CognitoTokens.fromIssuedTokens(
          accessToken: buildTestJwt({'sub': 'user-1'}),
          idToken: id,
          refreshToken: 'refresh',
        ),
        throwsFormatException,
      );
    });
  });
}
