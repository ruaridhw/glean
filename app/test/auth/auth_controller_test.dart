import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/auth_controller.dart';
import 'package:glean/auth/tokens.dart';
import 'package:glean/router/auth_state.dart';
import 'package:mocktail/mocktail.dart';

import 'support/fakes.dart';

void main() {
  late InMemoryTokenStorage storage;
  late MockCognitoAuthClient client;
  late ProviderContainer container;

  CognitoTokens tokensExpiringIn(
    Duration delta, {
    String sub = 'user-sub-123',
  }) => CognitoTokens(
    accessToken: 'access-1',
    refreshToken: 'refresh-1',
    idToken: 'id-1',
    userSub: sub,
    email: 'test@gmail.com',
    expiresAt: DateTime.now().add(delta),
  );

  ProviderContainer buildContainer(AuthSessionSnapshot seed) {
    final c = ProviderContainer(
      overrides: [
        authControllerProvider.overrideWith(
          () => AuthController.seeded(seed, storage: storage, client: client),
        ),
      ],
    );
    addTearDown(c.dispose);
    return c;
  }

  setUp(() {
    storage = InMemoryTokenStorage();
    client = MockCognitoAuthClient();
  });

  group('signIn', () {
    test('AC-AUTH-08: moves to active with the resolved user id and persists '
        'tokens, driven from the returned result', () async {
      final CognitoTokens tokens = tokensExpiringIn(const Duration(hours: 1));
      when(() => client.signIn()).thenAnswer((_) async => tokens);
      container = buildContainer(AuthSessionSnapshot.signedOut);

      await container.read(authControllerProvider.notifier).signIn();

      final AuthSessionSnapshot state = container.read(authControllerProvider);
      expect(state.status, AuthStatus.active);
      expect(state.userId, 'user-sub-123');
      expect(container.read(authStatusProvider), AuthStatus.active);
      expect(storage.saveTokensCalls, 1);
      expect(storage.accessToken, 'access-1');
    });
  });

  group('signOut', () {
    test(
      'AC-AUTH-03: clears storage explicitly and moves to signedOut',
      () async {
        storage.accessToken = 'access-1';
        storage.refreshToken = 'refresh-1';
        storage.userSub = 'user-sub-123';
        final CognitoTokens tokens = tokensExpiringIn(const Duration(hours: 1));
        container = buildContainer(
          AuthSessionSnapshot(
            status: AuthStatus.active,
            userId: 'user-sub-123',
            tokens: tokens,
          ),
        );

        await container.read(authControllerProvider.notifier).signOut();

        expect(storage.clearAllCalls, 1);
        expect(storage.userSub, isNull, reason: 'clearAll clears identity too');
        final AuthSessionSnapshot state = container.read(
          authControllerProvider,
        );
        expect(state.status, AuthStatus.signedOut);
        expect(state.userId, isNull);
        expect(container.read(authStatusProvider), AuthStatus.signedOut);
      },
    );

    test('does not call refresh/token collaborators at all', () async {
      final CognitoTokens tokens = tokensExpiringIn(const Duration(hours: 1));
      container = buildContainer(
        AuthSessionSnapshot(
          status: AuthStatus.active,
          userId: 'user-sub-123',
          tokens: tokens,
        ),
      );

      await container.read(authControllerProvider.notifier).signOut();

      verifyNever(() => client.refresh(any()));
      verifyNever(() => client.signIn());
    });
  });

  group('getValidAccessToken', () {
    test(
      'returns the cached token without refreshing when not expired',
      () async {
        final CognitoTokens tokens = tokensExpiringIn(const Duration(hours: 1));
        container = buildContainer(
          AuthSessionSnapshot(
            status: AuthStatus.active,
            userId: 'user-sub-123',
            tokens: tokens,
          ),
        );

        final String? result = await container
            .read(authControllerProvider.notifier)
            .getValidAccessToken();

        expect(result, 'access-1');
        verifyNever(() => client.refresh(any()));
      },
    );

    test(
      'refreshes and republishes active with the new token when expired',
      () async {
        final CognitoTokens expired = tokensExpiringIn(
          const Duration(seconds: -5),
        );
        final CognitoTokens refreshed = CognitoTokens(
          accessToken: 'access-2',
          refreshToken: 'refresh-1',
          idToken: 'id-2',
          userSub: 'user-sub-123',
          email: 'test@gmail.com',
          expiresAt: DateTime.now().add(const Duration(hours: 1)),
        );
        when(
          () => client.refresh('refresh-1'),
        ).thenAnswer((_) async => refreshed);
        container = buildContainer(
          AuthSessionSnapshot(
            status: AuthStatus.active,
            userId: 'user-sub-123',
            tokens: expired,
          ),
        );

        final String? result = await container
            .read(authControllerProvider.notifier)
            .getValidAccessToken();

        expect(result, 'access-2');
        expect(storage.accessToken, 'access-2');
        final AuthSessionSnapshot state = container.read(
          authControllerProvider,
        );
        expect(state.status, AuthStatus.active);
      },
    );

    test(
      'AC-AUTH-05 / AC-AUTH-04: a failed refresh moves to expired, keeps the '
      'user id, and never persists an empty/partial token',
      () async {
        final CognitoTokens expired = tokensExpiringIn(
          const Duration(seconds: -5),
        );
        // Storage starts holding the same tokens the controller was seeded
        // with, so this exercises the real "storage agrees" check rather
        // than storage merely staying at its blank initial state.
        storage.accessToken = expired.accessToken;
        storage.refreshToken = expired.refreshToken;
        storage.idToken = expired.idToken;
        storage.userSub = expired.userSub;
        storage.email = expired.email;
        storage.expiresAt = expired.expiresAt;
        when(() => client.refresh('refresh-1')).thenAnswer((_) async => null);
        container = buildContainer(
          AuthSessionSnapshot(
            status: AuthStatus.active,
            userId: 'user-sub-123',
            tokens: expired,
          ),
        );

        final String? result = await container
            .read(authControllerProvider.notifier)
            .getValidAccessToken();

        expect(result, isNull);
        final AuthSessionSnapshot state = container.read(
          authControllerProvider,
        );
        expect(state.status, AuthStatus.expired);
        expect(
          state.userId,
          'user-sub-123',
          reason: 'AC-AUTH-04: expired must still resolve a user id',
        );
        expect(container.read(authStatusProvider), AuthStatus.expired);

        // AC-AUTH-05: storage's own view of the world agrees — no lingering
        // usable access token, even though the identity survives.
        expect(storage.accessToken, isNull);
        expect(storage.refreshToken, isNull);
        expect(storage.userSub, 'user-sub-123');
        expect(storage.clearTokensKeepIdentityCalls, 1);
        expect(storage.clearAllCalls, 0);
      },
    );

    test('returns null with no session at all (never calls refresh)', () async {
      container = buildContainer(AuthSessionSnapshot.signedOut);

      final String? result = await container
          .read(authControllerProvider.notifier)
          .getValidAccessToken();

      expect(result, isNull);
      verifyNever(() => client.refresh(any()));
    });
  });

  group('the bare default constructor', () {
    test('fails loudly rather than silently no-op-ing when mutated', () async {
      final c = ProviderContainer();
      addTearDown(c.dispose);

      await expectLater(
        c.read(authControllerProvider.notifier).signIn(),
        throwsA(isA<UnimplementedError>()),
      );
    });
  });
}
