import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/auth/widgets/signed_out_banner.dart';
import 'package:glean/router/auth_state.dart';

void main() {
  Future<ProviderContainer> pumpBanner(
    WidgetTester tester,
    AuthStatus status,
  ) async {
    final ProviderContainer container = ProviderContainer();
    container.read(authStatusProvider.notifier).setStatus(status);
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          theme: gleanLightTheme,
          home: const Scaffold(body: SignedOutBanner()),
        ),
      ),
    );
    return container;
  }

  testWidgets('renders nothing while AI features are available (active)', (
    tester,
  ) async {
    await pumpBanner(tester, AuthStatus.active);
    await tester.pumpAndSettle();

    expect(find.textContaining('Signed out'), findsNothing);
  });

  testWidgets('AC-AUTH-04: shows the banner when the session has expired', (
    tester,
  ) async {
    await pumpBanner(tester, AuthStatus.expired);
    await tester.pumpAndSettle();

    expect(find.textContaining('Signed out'), findsOneWidget);
    expect(
      find.textContaining('Your saved data is still here'),
      findsOneWidget,
    );
  });

  testWidgets('shows the banner when genuinely signed out too (defensive)', (
    tester,
  ) async {
    await pumpBanner(tester, AuthStatus.signedOut);
    await tester.pumpAndSettle();

    expect(find.textContaining('Signed out'), findsOneWidget);
  });

  testWidgets(
    'AC-TRN-04: cross-fades in when status flips from active to expired',
    (tester) async {
      final ProviderContainer container = await pumpBanner(
        tester,
        AuthStatus.active,
      );
      expect(find.textContaining('Signed out'), findsNothing);

      container.read(authStatusProvider.notifier).setStatus(AuthStatus.expired);
      await tester.pump();

      // Mid-transition: AnimatedSwitcher is cross-fading, not popping instantly.
      expect(find.byType(AnimatedSwitcher), findsOneWidget);
      await tester.pumpAndSettle();
      expect(find.textContaining('Signed out'), findsOneWidget);
    },
  );
}
