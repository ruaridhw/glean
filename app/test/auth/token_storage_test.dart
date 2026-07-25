import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/token_storage.dart';
import 'package:glean/auth/tokens.dart';

import 'support/fakes.dart';

void main() {
  group('InMemoryTokenStorage (TokenStorage contract)', () {
    late InMemoryTokenStorage storage;
    late CognitoTokens tokens;

    setUp(() {
      storage = InMemoryTokenStorage();
      tokens = CognitoTokens(
        accessToken: 'access-123',
        refreshToken: 'refresh-123',
        idToken: 'id-123',
        userSub: 'user-sub-123',
        email: 'test@gmail.com',
        expiresAt: DateTime.utc(2030),
      );
    });

    test('saveTokens then readTokens round-trips every field', () async {
      await storage.saveTokens(tokens);
      final StoredTokenValues stored = await storage.readTokens();

      expect(stored.accessToken, 'access-123');
      expect(stored.refreshToken, 'refresh-123');
      expect(stored.idToken, 'id-123');
      expect(stored.userSub, 'user-sub-123');
      expect(stored.email, 'test@gmail.com');
      expect(stored.expiresAt, DateTime.utc(2030));
    });

    test('clearAll removes every field, including identity', () async {
      await storage.saveTokens(tokens);
      await storage.clearAll();
      final StoredTokenValues stored = await storage.readTokens();

      expect(stored.accessToken, isNull);
      expect(stored.refreshToken, isNull);
      expect(stored.idToken, isNull);
      expect(
        stored.userSub,
        isNull,
        reason: 'AC-AUTH-03: sign-out clears everything',
      );
      expect(stored.email, isNull);
      expect(stored.expiresAt, isNull);
    });

    test('clearTokensKeepIdentity clears tokens but keeps userSub/email '
        '(AC-AUTH-04)', () async {
      await storage.saveTokens(tokens);
      await storage.clearTokensKeepIdentity();
      final StoredTokenValues stored = await storage.readTokens();

      expect(stored.accessToken, isNull);
      expect(stored.refreshToken, isNull);
      expect(stored.idToken, isNull);
      expect(stored.expiresAt, isNull);
      expect(stored.userSub, 'user-sub-123');
      expect(stored.email, 'test@gmail.com');
    });
  });
}
