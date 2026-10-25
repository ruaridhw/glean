import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/token_storage.dart';
import 'package:glean/auth/tokens.dart';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  group('TokenStorage through the secure-storage plugin boundary', () {
    late TokenStorage storage;
    late CognitoTokens tokens;

    setUp(() {
      FlutterSecureStorage.setMockInitialValues({'unrelated_key': 'keep'});
      storage = TokenStorage();
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
      expect(stored.userSub, isNull, reason: 'sign-out clears everything');
      expect(stored.email, isNull);
      expect(stored.expiresAt, isNull);
      expect(
        await const FlutterSecureStorage().read(key: 'unrelated_key'),
        'keep',
      );
    });

    test(
      'clearAll removes the household data kept beside the tokens',
      () async {
        const FlutterSecureStorage secure = FlutterSecureStorage();
        await secure.write(
          key: '${TokenStorage.userDataKeyPrefix}week_feedback.user-sub-123',
          value: '{}',
        );
        await storage.saveTokens(tokens);

        await storage.clearAll();

        expect(await secure.readAll(), <String, String>{
          'unrelated_key': 'keep',
        });
      },
    );

    test(
      'clearAll still removes the tokens when listing the household data fails',
      () async {
        final TokenStorage failing = TokenStorage(
          secureStorage: _ReadAllFails(),
        );
        await failing.saveTokens(tokens);

        await failing.clearAll();

        final StoredTokenValues stored = await failing.readTokens();
        expect(stored.accessToken, isNull);
        expect(stored.refreshToken, isNull);
        expect(stored.userSub, isNull);
      },
    );

    test('clearTokensKeepIdentity keeps the household data', () async {
      const FlutterSecureStorage secure = FlutterSecureStorage();
      const String key =
          '${TokenStorage.userDataKeyPrefix}week_feedback.user-sub-123';
      await secure.write(key: key, value: '{}');

      await storage.clearTokensKeepIdentity();

      expect(await secure.read(key: key), '{}');
    });

    test(
      'clearTokensKeepIdentity clears tokens but keeps userSub/email',
      () async {
        await storage.saveTokens(tokens);
        await storage.clearTokensKeepIdentity();
        final StoredTokenValues stored = await storage.readTokens();

        expect(stored.accessToken, isNull);
        expect(stored.refreshToken, isNull);
        expect(stored.idToken, isNull);
        expect(stored.expiresAt, isNull);
        expect(stored.userSub, 'user-sub-123');
        expect(stored.email, 'test@gmail.com');
      },
    );
  });
}

/// The plugin's in-memory store, except that listing every key fails.
class _ReadAllFails extends FlutterSecureStorage {
  @override
  Future<Map<String, String>> readAll({
    AppleOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    AppleOptions? mOptions,
    WindowsOptions? wOptions,
  }) async => throw PlatformException(code: 'keystore', message: 'unavailable');
}
