import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/auth_controller.dart';
import 'package:glean/auth/token_storage.dart';
import 'package:glean/auth/tokens.dart';
import 'package:glean/router/auth_state.dart';
import 'package:mocktail/mocktail.dart';
import 'support/fakes.dart';

class HoldingStorage extends TokenStorage {
  final started = Completer<void>();
  final release = Completer<void>();
  @override
  Future<void> saveTokens(CognitoTokens tokens) async {
    started.complete();
    await release.future;
    await super.saveTokens(tokens);
  }
}

class CountingStorage extends TokenStorage {
  int saveTokensCalls = 0;
  @override
  Future<void> saveTokens(CognitoTokens tokens) {
    saveTokensCalls += 1;
    return super.saveTokens(tokens);
  }
}

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues(<String, String>{}));
  final expired = CognitoTokens(
    accessToken: 'old',
    refreshToken: 'refresh',
    idToken: 'id',
    userSub: 'a',
    email: '',
    expiresAt: DateTime(2000),
  );
  final fresh = CognitoTokens(
    accessToken: 'new',
    refreshToken: 'refresh',
    idToken: 'id',
    userSub: 'a',
    email: '',
    expiresAt: DateTime(2100),
  );
  test(
    'logout clears an already-started storage write even if a later sign-in fails',
    () async {
      final storage = HoldingStorage();
      final client = MockCognitoAuthClient();
      when(() => client.refresh('refresh')).thenAnswer((_) async => fresh);
      when(() => client.signIn()).thenThrow(StateError('cancelled'));
      final container = ProviderContainer(
        overrides: [
          authControllerProvider.overrideWith(
            () => AuthController(
              AuthSessionSnapshot(
                status: AuthStatus.active,
                userId: 'a',
                tokens: expired,
              ),
              storage: storage,
              client: client,
            ),
          ),
        ],
      );
      addTearDown(container.dispose);
      final controller = container.read(authControllerProvider.notifier);
      final refresh = controller.getValidAccessToken();
      await storage.started.future;
      final logout = controller.signOut();
      await expectLater(controller.signIn(), throwsStateError);
      storage.release.complete();
      expect(await refresh, isNull);
      await logout;
      expect(
        container.read(authControllerProvider).status,
        AuthStatus.signedOut,
      );
      expect((await storage.readTokens()).accessToken, isNull);
      expect((await storage.readTokens()).userSub, isNull);
    },
  );

  test(
    'concurrent API callers share one refresh and persist one rotated token',
    () async {
      final storage = CountingStorage();
      final client = MockCognitoAuthClient();
      final response = Completer<CognitoTokens?>();
      when(() => client.refresh('refresh')).thenAnswer((_) => response.future);
      final container = ProviderContainer(
        overrides: [
          authControllerProvider.overrideWith(
            () => AuthController(
              AuthSessionSnapshot(
                status: AuthStatus.active,
                userId: 'a',
                tokens: expired,
              ),
              storage: storage,
              client: client,
            ),
          ),
        ],
      );
      addTearDown(container.dispose);
      final controller = container.read(authControllerProvider.notifier);
      final first = controller.getValidAccessToken();
      final second = controller.getValidAccessToken();
      response.complete(fresh);
      expect(await Future.wait([first, second]), ['new', 'new']);
      verify(() => client.refresh('refresh')).called(1);
      expect(storage.saveTokensCalls, 1);
    },
  );

  test(
    'identity-only storage after expiry reopens local data as expired, not signed out',
    () async {
      final storage = TokenStorage();
      await storage.saveTokens(expired);
      await storage.clearTokensKeepIdentity();
      final snapshot = await loadInitialAuthSnapshot(storage);
      expect(snapshot.status, AuthStatus.expired);
      expect(snapshot.userId, 'a');
      expect(snapshot.tokens, isNull);
    },
  );

  test(
    'logout invalidates a pending refresh before it can restore identity or tokens',
    () async {
      final storage = TokenStorage();
      await storage.saveTokens(expired);
      final client = MockCognitoAuthClient();
      final response = Completer<CognitoTokens?>();
      when(() => client.refresh('refresh')).thenAnswer((_) => response.future);
      final container = ProviderContainer(
        overrides: [
          authControllerProvider.overrideWith(
            () => AuthController(
              AuthSessionSnapshot(
                status: AuthStatus.active,
                userId: 'a',
                tokens: expired,
              ),
              storage: storage,
              client: client,
            ),
          ),
        ],
      );
      addTearDown(container.dispose);
      final controller = container.read(authControllerProvider.notifier);
      final pending = controller.getValidAccessToken();
      await controller.signOut();
      response.complete(fresh);
      expect(await pending, isNull);
      expect(
        container.read(authControllerProvider).status,
        AuthStatus.signedOut,
      );
      expect((await storage.readTokens()).userSub, isNull);
      expect((await storage.readTokens()).accessToken, isNull);
    },
  );
}
