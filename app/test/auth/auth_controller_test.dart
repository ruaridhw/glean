import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/auth/auth.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:mocktail/mocktail.dart';

import 'support/fakes.dart';

void main() {
  late TokenStorage storage;
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
          () => AuthController(seed, storage: storage, client: client),
        ),
      ],
    );
    addTearDown(c.dispose);
    return c;
  }

  setUp(() {
    FlutterSecureStorage.setMockInitialValues(<String, String>{});
    storage = TokenStorage();
    client = MockCognitoAuthClient();
  });

  group('signIn', () {
    test('moves to active with the resolved user id and persists tokens, '
        'driven from the returned result', () async {
      final CognitoTokens tokens = tokensExpiringIn(const Duration(hours: 1));
      when(() => client.signIn()).thenAnswer((_) async => tokens);
      container = buildContainer(AuthSessionSnapshot.signedOut);

      await container.read(authControllerProvider.notifier).signIn();

      final AuthSessionSnapshot state = container.read(authControllerProvider);
      expect(state.status, AuthStatus.active);
      expect(state.userId, 'user-sub-123');
      expect(container.read(authStatusProvider), AuthStatus.active);
      expect((await storage.readTokens()).accessToken, 'access-1');
    });
  });

  group('signOut', () {
    test('clears storage explicitly and moves to signedOut', () async {
      final CognitoTokens tokens = tokensExpiringIn(const Duration(hours: 1));
      await storage.saveTokens(tokens);
      container = buildContainer(
        AuthSessionSnapshot(
          status: AuthStatus.active,
          userId: 'user-sub-123',
          tokens: tokens,
        ),
      );

      await container.read(authControllerProvider.notifier).signOut();

      final StoredTokenValues stored = await storage.readTokens();
      expect(stored.accessToken, isNull);
      expect(stored.refreshToken, isNull);
      expect(stored.userSub, isNull, reason: 'sign-out clears identity too');
      final AuthSessionSnapshot state = container.read(authControllerProvider);
      expect(state.status, AuthStatus.signedOut);
      expect(state.userId, isNull);
      expect(container.read(authStatusProvider), AuthStatus.signedOut);
    });

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
        expect((await storage.readTokens()).accessToken, 'access-2');
        final AuthSessionSnapshot state = container.read(
          authControllerProvider,
        );
        expect(state.status, AuthStatus.active);
      },
    );

    test('a failed refresh moves to expired, keeps the user id, and never '
        'persists an empty/partial token', () async {
      final CognitoTokens expired = tokensExpiringIn(
        const Duration(seconds: -5),
      );
      // Storage starts holding the same tokens the controller was seeded
      // with, so this exercises the real "storage agrees" check rather
      // than storage merely staying at its blank initial state.
      await storage.saveTokens(expired);
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
      final AuthSessionSnapshot state = container.read(authControllerProvider);
      expect(state.status, AuthStatus.expired);
      expect(
        state.userId,
        'user-sub-123',
        reason: 'expired must still resolve a user id',
      );
      expect(container.read(authStatusProvider), AuthStatus.expired);

      // Storage's own view of the world agrees — no lingering usable
      // access token, even though the identity survives.
      final StoredTokenValues stored = await storage.readTokens();
      expect(stored.accessToken, isNull);
      expect(stored.refreshToken, isNull);
      expect(stored.idToken, isNull);
      expect(stored.expiresAt, isNull);
      expect(stored.userSub, 'user-sub-123');
      expect(stored.email, 'test@gmail.com');
    });

    test('returns null with no session at all (never calls refresh)', () async {
      container = buildContainer(AuthSessionSnapshot.signedOut);

      final String? result = await container
          .read(authControllerProvider.notifier)
          .getValidAccessToken();

      expect(result, isNull);
      verifyNever(() => client.refresh(any()));
    });
  });

  group('providers derived from the controller', () {
    test('an active session resolves the user id, a valid token, and active '
        'status', () async {
      container = buildContainer(
        AuthSessionSnapshot(
          status: AuthStatus.active,
          userId: 'user-sub-123',
          tokens: tokensExpiringIn(const Duration(hours: 1)),
        ),
      );

      expect(container.read(currentUserIdProvider), 'user-sub-123');
      expect(container.read(authStatusProvider), AuthStatus.active);
      expect(container.read(aiFeaturesAvailableProvider), isTrue);
      expect(await container.read(apiAccessTokenProvider)(), 'access-1');
    });

    test('currentUserIdProvider throws while genuinely signed out', () {
      container = buildContainer(AuthSessionSnapshot.signedOut);

      // Riverpod wraps a build-time throw in its own exception type, so
      // assert on the propagated message.
      expect(
        () => container.read(currentUserIdProvider),
        throwsA(
          predicate<Object>(
            (Object e) => e.toString().contains('read while signed out'),
          ),
        ),
      );
    });

    test('a failed refresh reached through apiAccessTokenProvider still leaves '
        'currentUserIdProvider resolving, with status expired', () async {
      when(() => client.refresh(any())).thenAnswer((_) async => null);
      container = buildContainer(
        AuthSessionSnapshot(
          status: AuthStatus.active,
          userId: 'user-sub-123',
          tokens: tokensExpiringIn(const Duration(seconds: -5)),
        ),
      );

      expect(await container.read(apiAccessTokenProvider)(), isNull);
      expect(container.read(authStatusProvider), AuthStatus.expired);
      expect(container.read(aiFeaturesAvailableProvider), isFalse);
      expect(
        container.read(currentUserIdProvider),
        'user-sub-123',
        reason: 'local reads must keep working through an expired session',
      );
    });

    test('an unoverridden authControllerProvider fails loudly, naming where '
        'to override it', () {
      final c = ProviderContainer();
      addTearDown(c.dispose);

      expect(
        () => c.read(authControllerProvider),
        throwsA(
          predicate<Object>(
            (Object e) => e.toString().contains('main.dart / main_e2e.dart'),
          ),
        ),
      );
    });
  });
}
