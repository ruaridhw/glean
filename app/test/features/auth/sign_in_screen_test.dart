import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/auth_controller.dart';
import 'package:glean/auth/cognito_auth_client.dart';
import 'package:glean/auth/tokens.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/auth/sign_in_screen.dart';
import 'package:mocktail/mocktail.dart';

import '../../auth/support/fakes.dart';

void main() {
  late InMemoryTokenStorage storage;
  late MockCognitoAuthClient client;
  late RecordingHaptics haptics;

  setUp(() {
    storage = InMemoryTokenStorage();
    client = MockCognitoAuthClient();
    haptics = RecordingHaptics();
  });

  Future<void> pumpSignIn(WidgetTester tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(
            () => AuthController.seeded(
              AuthSessionSnapshot.signedOut,
              storage: storage,
              client: client,
            ),
          ),
          hapticsProvider.overrideWithValue(haptics),
        ],
        child: MaterialApp(theme: gleanLightTheme, home: const SignInScreen()),
      ),
    );
  }

  testWidgets('renders the "Sign in" label and the Google button', (
    tester,
  ) async {
    await pumpSignIn(tester);

    expect(find.text('Sign in'), findsOneWidget);
    expect(find.text('Sign in with Google'), findsOneWidget);
  });

  testWidgets('does not cite Terms or a Privacy Policy that are not hosted '
      'yet', (tester) async {
    await pumpSignIn(tester);

    expect(find.textContaining('Terms of Service'), findsNothing);
    expect(find.textContaining('Privacy Policy'), findsNothing);
  });

  testWidgets(
    'AC-HAP-05: the tap fires exactly one lightImpact immediately, before '
    'sign-in resolves',
    (tester) async {
      final Completer<CognitoTokens> pending = Completer<CognitoTokens>();
      when(() => client.signIn()).thenAnswer((_) => pending.future);
      await pumpSignIn(tester);

      await tester.tap(find.text('Sign in with Google'));
      await tester.pump();

      expect(haptics.calls, <HapticWeight>[HapticWeight.light]);

      pending.complete(
        CognitoTokens(
          accessToken: 'a',
          refreshToken: 'r',
          idToken: 'i',
          userSub: 'user-sub-123',
          email: 'test@gmail.com',
          expiresAt: DateTime.now().add(const Duration(hours: 1)),
        ),
      );
      await tester.pumpAndSettle();
    },
  );

  testWidgets(
    'a successful sign-in fires exactly light then medium, and no more',
    (tester) async {
      when(() => client.signIn()).thenAnswer(
        (_) async => CognitoTokens(
          accessToken: 'a',
          refreshToken: 'r',
          idToken: 'i',
          userSub: 'user-sub-123',
          email: 'test@gmail.com',
          expiresAt: DateTime.now().add(const Duration(hours: 1)),
        ),
      );
      await pumpSignIn(tester);

      await tester.tap(find.text('Sign in with Google'));
      await tester.pumpAndSettle();

      expect(haptics.calls, <HapticWeight>[
        HapticWeight.light,
        HapticWeight.medium,
      ]);
    },
  );

  testWidgets(
    'a non-cancelled failure shows a snackbar and fires only the tap haptic',
    (tester) async {
      when(
        () => client.signIn(),
      ).thenThrow(const AuthException('Sign-in failed: network error'));
      await pumpSignIn(tester);

      await tester.tap(find.text('Sign in with Google'));
      await tester.pumpAndSettle();

      expect(find.text('Sign-in failed: network error'), findsOneWidget);
      expect(haptics.calls, <HapticWeight>[HapticWeight.light]);
    },
  );

  testWidgets(
    'a cancelled sign-in shows no snackbar and does not fire a second haptic',
    (tester) async {
      when(() => client.signIn()).thenThrow(
        const AuthException('Sign-in was cancelled.', cancelled: true),
      );
      await pumpSignIn(tester);

      await tester.tap(find.text('Sign in with Google'));
      await tester.pumpAndSettle();

      expect(find.byType(SnackBar), findsNothing);
      expect(haptics.calls, <HapticWeight>[HapticWeight.light]);
    },
  );
}
