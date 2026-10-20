import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/auth_bypass.dart';
import 'package:glean/auth/auth.dart';

void main() {
  group('bypassAuthSnapshot', () {
    test('is always active and resolves a stable identity', () {
      final AuthSessionSnapshot snapshot = bypassAuthSnapshot();

      expect(snapshot.status, AuthStatus.active);
      expect(snapshot.userId, kAuthBypassUserSub);
      expect(
        snapshot.tokens,
        isNull,
        reason:
            'bypass has no tokens at all — every backend LLM router still '
            'requires a valid one, so a bypass build cannot call one',
      );
    });

    test('honours a custom identity', () {
      final AuthSessionSnapshot snapshot = bypassAuthSnapshot(
        userId: 'ci-e2e-user-sub',
      );
      expect(snapshot.userId, 'ci-e2e-user-sub');
    });
  });

  group('bypassAuthSnapshotWithTokens', () {
    test('is active as the token\'s subject and carries the tokens', () {
      final CognitoTokens tokens = CognitoTokens(
        accessToken: 'a',
        refreshToken: 'r',
        idToken: 'i',
        userSub: 'test-user-sub',
        email: '',
        expiresAt: DateTime.now().add(const Duration(hours: 1)),
      );
      final AuthSessionSnapshot snapshot = bypassAuthSnapshotWithTokens(tokens);
      expect(snapshot.status, AuthStatus.active);
      expect(snapshot.userId, 'test-user-sub');
      expect(snapshot.tokens, same(tokens));
    });
  });

  group('assertAuthBypassUnreachable', () {
    test('throws for a production-looking API base URL', () {
      expect(
        () => assertAuthBypassUnreachable(
          'https://abc123.execute-api.eu-west-2.amazonaws.com',
        ),
        throwsA(isA<StateError>()),
      );
    });

    test('does not throw for local/loopback API base URLs', () {
      expect(
        () => assertAuthBypassUnreachable('http://localhost:8000'),
        returnsNormally,
      );
      expect(
        () => assertAuthBypassUnreachable('http://10.0.2.2:8000'),
        returnsNormally,
      );
    });
  });
}
