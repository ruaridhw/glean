import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/token_storage.dart';
import 'package:glean/auth/tokens.dart';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  group('SecureTokenStorage through the secure-storage plugin boundary', () {
    late SecureTokenStorage storage;
    late CognitoTokens tokens;

    setUp(() {
      FlutterSecureStorage.setMockInitialValues({'unrelated_key': 'keep'});
      storage = SecureTokenStorage();
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
      expect(
        await const FlutterSecureStorage().read(key: 'unrelated_key'),
        'keep',
      );
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
