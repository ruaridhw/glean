// Exercises the actual override factory used by the production entrypoint.
// Tests do not re-create the user/token/sign-out wiring inside their fixtures.
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/auth/auth_controller.dart';
import 'package:glean/auth/tokens.dart';
import 'package:glean/auth/session_overrides.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/features/settings/providers/sign_out_action.dart';
import 'package:glean/router/auth_state.dart';
import 'package:mocktail/mocktail.dart';

import 'support/fakes.dart';

void main() {
  late InMemoryTokenStorage storage;
  late MockCognitoAuthClient client;

  CognitoTokens tokensExpiringIn(Duration delta) => CognitoTokens(
    accessToken: 'access-1',
    refreshToken: 'refresh-1',
    idToken: 'id-1',
    userSub: 'user-sub-123',
    email: 'test@gmail.com',
    expiresAt: DateTime.now().add(delta),
  );

  ProviderContainer buildContainer(AuthSessionSnapshot snapshot) {
    final ProviderContainer container = ProviderContainer(
      overrides: sessionOverrides(snapshot, storage: storage, client: client),
    );
    addTearDown(container.dispose);
    return container;
  }

  setUp(() {
    storage = InMemoryTokenStorage();
    client = MockCognitoAuthClient();
  });

  test(
    'an active session resolves the user id, a valid token, and active status',
    () async {
      final CognitoTokens tokens = tokensExpiringIn(const Duration(hours: 1));
      final ProviderContainer container = buildContainer(
        AuthSessionSnapshot(
          status: AuthStatus.active,
          userId: 'user-sub-123',
          tokens: tokens,
        ),
      );

      expect(container.read(currentUserIdProvider), 'user-sub-123');
      expect(container.read(authStatusProvider), AuthStatus.active);
      final String? accessToken = await container.read(
        apiAccessTokenProvider,
      )();
      expect(accessToken, 'access-1');
    },
  );

  test('currentUserIdProvider throws while genuinely signed out', () {
    final ProviderContainer container = buildContainer(
      AuthSessionSnapshot.signedOut,
    );

    // Riverpod wraps a provider-build-time throw in its own `ProviderException`
    // (not itself part of `flutter_riverpod`'s public export surface — see
    // FINDINGS.md F-03 for the same "not exported" issue with `Override`), so
    // this asserts on the propagated message rather than naming that type.
    expect(
      () => container.read(currentUserIdProvider),
      throwsA(
        predicate<Object>(
          (Object e) => e.toString().contains('read while signed out'),
        ),
      ),
    );
  });

  test(
    'signOutActionProvider (Settings\' seam) clears tokens and flips '
    'authStatusProvider — AC-AUTH-03 through the real integration point',
    () async {
      storage.accessToken = 'access-1';
      storage.userSub = 'user-sub-123';
      final CognitoTokens tokens = tokensExpiringIn(const Duration(hours: 1));
      final ProviderContainer container = buildContainer(
        AuthSessionSnapshot(
          status: AuthStatus.active,
          userId: 'user-sub-123',
          tokens: tokens,
        ),
      );

      await container.read(signOutActionProvider)();

      expect(storage.clearAllCalls, 1);
      expect(container.read(authStatusProvider), AuthStatus.signedOut);
    },
  );

  test(
    'AC-AUTH-04: a failed refresh reached through apiAccessTokenProvider '
    'still leaves currentUserIdProvider resolving, with status expired',
    () async {
      final CognitoTokens expired = tokensExpiringIn(
        const Duration(seconds: -5),
      );
      when(() => client.refresh(any())).thenAnswer((_) async => null);
      final ProviderContainer container = buildContainer(
        AuthSessionSnapshot(
          status: AuthStatus.active,
          userId: 'user-sub-123',
          tokens: expired,
        ),
      );

      final String? token = await container.read(apiAccessTokenProvider)();

      expect(token, isNull);
      expect(container.read(authStatusProvider), AuthStatus.expired);
      expect(
        container.read(currentUserIdProvider),
        'user-sub-123',
        reason: 'local reads must keep working through an expired session',
      );
    },
  );
}
