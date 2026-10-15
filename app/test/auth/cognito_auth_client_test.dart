import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/cognito_auth_client.dart';
import 'package:mocktail/mocktail.dart';

import 'support/fakes.dart';

void main() {
  setUpAll(registerAuthFallbackValues);

  late MockFlutterAppAuth appAuth;
  late CognitoAuthClient client;

  setUp(() {
    appAuth = MockFlutterAppAuth();
    client = CognitoAuthClient(
      cognitoDomain: 'auth.example.com',
      clientId: 'client-123',
      appAuth: appAuth,
    );
  });

  String idTokenFor(String sub, [String email = 'test@gmail.com']) =>
      buildTestJwt(<String, dynamic>{'sub': sub, 'email': email});

  group('signIn', () {
    test('consumes the AppAuth call\'s returned result directly, exactly '
        'once, with no other interaction', () async {
      when(() => appAuth.authorizeAndExchangeCode(any())).thenAnswer(
        (_) async => AuthorizationTokenResponse(
          'access-123',
          'refresh-123',
          DateTime.now().add(const Duration(hours: 1)),
          idTokenFor('user-sub-123'),
          'Bearer',
          null,
          null,
          null,
        ),
      );

      final tokens = await client.signIn();

      expect(tokens.accessToken, 'access-123');
      expect(tokens.refreshToken, 'refresh-123');
      expect(tokens.userSub, 'user-sub-123');
      expect(tokens.email, 'test@gmail.com');
      verify(() => appAuth.authorizeAndExchangeCode(any())).called(1);
      verifyNoMoreInteractions(appAuth);
    });

    test(
      'sends the redirect URI, Google IdP and PKCE-relevant config',
      () async {
        when(() => appAuth.authorizeAndExchangeCode(any())).thenAnswer(
          (_) async => AuthorizationTokenResponse(
            'access-123',
            'refresh-123',
            DateTime.now().add(const Duration(hours: 1)),
            idTokenFor('user-sub-123'),
            'Bearer',
            null,
            null,
            null,
          ),
        );

        await client.signIn();

        final AuthorizationTokenRequest request =
            verify(
                  () => appAuth.authorizeAndExchangeCode(captureAny()),
                ).captured.single
                as AuthorizationTokenRequest;
        expect(request.redirectUrl, 'glean://auth/callback');
        expect(request.clientId, 'client-123');
        expect(request.additionalParameters?['identity_provider'], 'Google');
        expect(
          request.scopes,
          containsAll(<String>['openid', 'email', 'profile']),
        );
      },
    );

    test(
      'wraps a cancelled sign-in as a distinguishable AuthException',
      () async {
        when(() => appAuth.authorizeAndExchangeCode(any())).thenThrow(
          FlutterAppAuthUserCancelledException(
            code: 'cancelled',
            platformErrorDetails: FlutterAppAuthPlatformErrorDetails(),
          ),
        );

        await expectLater(
          client.signIn(),
          throwsA(
            isA<AuthException>().having(
              (e) => e.cancelled,
              'cancelled',
              isTrue,
            ),
          ),
        );
      },
    );

    test('throws when the response is missing a required token', () async {
      when(() => appAuth.authorizeAndExchangeCode(any())).thenAnswer(
        (_) async => AuthorizationTokenResponse(
          'access-123',
          null, // no refresh token
          DateTime.now().add(const Duration(hours: 1)),
          idTokenFor('user-sub-123'),
          'Bearer',
          null,
          null,
          null,
        ),
      );

      await expectLater(
        client.signIn(),
        throwsA(
          isA<AuthException>().having((e) => e.cancelled, 'cancelled', isFalse),
        ),
      );
    });
  });

  group('refresh', () {
    test('returns new tokens, reusing the old refresh token when Cognito '
        'omits one from the response', () async {
      when(() => appAuth.token(any())).thenAnswer(
        (_) async => TokenResponse(
          'new-access',
          null, // Cognito's refresh grant doesn't reissue one
          DateTime.now().add(const Duration(hours: 1)),
          idTokenFor('user-sub-123'),
          'Bearer',
          null,
          null,
        ),
      );

      final tokens = await client.refresh('old-refresh-token');

      expect(tokens, isNotNull);
      expect(tokens!.accessToken, 'new-access');
      expect(tokens.refreshToken, 'old-refresh-token');
    });

    test('returns null (never throws, never a partial token) when the '
        'platform call itself fails', () async {
      when(() => appAuth.token(any())).thenThrow(Exception('network down'));

      final tokens = await client.refresh('old-refresh-token');

      expect(tokens, isNull);
    });

    test('returns null for a structurally-successful response with an '
        'empty/missing access token', () async {
      when(() => appAuth.token(any())).thenAnswer(
        (_) async => TokenResponse(
          '', // "succeeded" but the access token is empty
          null,
          DateTime.now().add(const Duration(hours: 1)),
          idTokenFor('user-sub-123'),
          'Bearer',
          null,
          null,
        ),
      );

      final tokens = await client.refresh('old-refresh-token');

      expect(tokens, isNull);
    });

    test(
      'returns null when the response has no id token to decode a sub from',
      () async {
        when(() => appAuth.token(any())).thenAnswer(
          (_) async => TokenResponse(
            'new-access',
            null,
            DateTime.now().add(const Duration(hours: 1)),
            null,
            'Bearer',
            null,
            null,
          ),
        );

        final tokens = await client.refresh('old-refresh-token');

        expect(tokens, isNull);
      },
    );
  });
}
