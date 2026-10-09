// Port of the Expo app's tests/auth/mode.test.ts (see git history),
// adapted for the structural (not
// flag-based) bypass §5 requires — see lib/auth/auth_mode.dart's top doc
// comment for exactly what changed and why.
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/auth_mode.dart';

void main() {
  group('resolveAuthSession', () {
    test(
      'a bypass identity is always authenticated, with no tokens at all',
      () {
        final AuthSession session = resolveAuthSession(
          stored: const StoredAuthValues(),
          bypassUserId: 'e2e-user-sub',
        );

        expect(
          session,
          const AuthSession(
            authenticated: true,
            accessToken: null,
            refreshToken: null,
            userSub: 'e2e-user-sub',
            source: AuthSessionSource.bypass,
          ),
        );
      },
    );

    test('a bypass identity wins even when stored tokens also exist', () {
      final AuthSession session = resolveAuthSession(
        stored: const StoredAuthValues(
          accessToken: 'stored-access',
          refreshToken: 'stored-refresh',
          userSub: 'stored-sub',
        ),
        bypassUserId: 'e2e-user-sub',
      );

      expect(session.source, AuthSessionSource.bypass);
      expect(session.userSub, 'e2e-user-sub');
    });

    test('authenticates from a stored, non-empty access token', () {
      final AuthSession session = resolveAuthSession(
        stored: const StoredAuthValues(
          accessToken: 'access-123',
          refreshToken: 'refresh-123',
          userSub: 'user-sub-123',
        ),
      );

      expect(
        session,
        const AuthSession(
          authenticated: true,
          accessToken: 'access-123',
          refreshToken: 'refresh-123',
          userSub: 'user-sub-123',
          source: AuthSessionSource.tokens,
        ),
      );
    });

    test('does not authenticate with no stored tokens and no bypass', () {
      final AuthSession session = resolveAuthSession(
        stored: const StoredAuthValues(),
      );

      expect(
        session,
        const AuthSession(
          authenticated: false,
          accessToken: null,
          refreshToken: null,
          userSub: null,
          source: AuthSessionSource.tokens,
        ),
      );
    });

    test('an empty-string access token does not count as authenticated', () {
      final AuthSession session = resolveAuthSession(
        stored: const StoredAuthValues(accessToken: ''),
      );

      expect(session.authenticated, isFalse);
    });
  });

  group('isProductionApiBaseUrl', () {
    test('treats localhost and loopback hosts as non-production', () {
      expect(isProductionApiBaseUrl('http://localhost:8000'), isFalse);
      expect(isProductionApiBaseUrl('http://127.0.0.1:8000'), isFalse);
      // The Android emulator's alias for the host machine's localhost.
      expect(isProductionApiBaseUrl('http://10.0.2.2:8000'), isFalse);
    });

    test('treats a real deployed backend as production', () {
      expect(
        isProductionApiBaseUrl(
          'https://abc123.execute-api.eu-west-2.amazonaws.com',
        ),
        isTrue,
      );
    });

    test('fails safe for an unparseable base URL', () {
      expect(isProductionApiBaseUrl(''), isTrue);
      expect(isProductionApiBaseUrl('not a url'), isTrue);
    });
  });
}
