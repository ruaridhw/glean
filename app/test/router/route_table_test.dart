// Route-table structure (AC-TEST-14): the five tab branches exist, every
// route resolves to real content, names are unique, and the intake flow
// resolves outside the tab shell (no `NavigationBar` while it's active).

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/auth_state.dart';
import 'package:glean/router/router.dart';
import 'package:go_router/go_router.dart';

void main() {
  group('AppRoutes structure', () {
    test('exactly five tab branches, landing on Pantry', () {
      expect(AppRoutes.tabBranchRoots, hasLength(5));
      expect(AppRoutes.tabBranchRoots.first.path, AppRoutes.pantry.path);
    });

    test('every route name is unique', () {
      final names = AppRoutes.all.map((route) => route.name).toList();
      expect(names.toSet(), hasLength(names.length));
    });

    test('intake routes live outside the tab shell paths', () {
      final tabPaths = AppRoutes.tabBranchRoots
          .map((route) => route.path)
          .toSet();
      for (final route in AppRoutes.intakeRoutes) {
        expect(
          tabPaths.contains(route.path),
          isFalse,
          reason: '${route.path} is a tab root',
        );
        expect(route.path, startsWith('/intake/'));
      }
    });
  });

  group('goRouterProvider resolves every route', () {
    late ProviderContainer container;
    late GoRouter router;

    setUp(() {
      container = ProviderContainer();
      router = container.read(goRouterProvider);
    });

    tearDown(() => container.dispose());

    Future<void> pumpAt(WidgetTester tester, String location) async {
      router.go(location);
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();
    }

    testWidgets('each tab branch root renders its placeholder', (tester) async {
      await pumpAt(tester, AppRoutes.pantry.path);
      expect(find.text('Pantry screen'), findsWidgets);

      await pumpAt(tester, AppRoutes.meals.path);
      expect(find.text('Meals screen'), findsWidgets);

      await pumpAt(tester, AppRoutes.plan.path);
      expect(find.text('Plan screen'), findsWidgets);

      await pumpAt(tester, AppRoutes.shop.path);
      expect(find.text('Shop screen'), findsWidgets);

      await pumpAt(tester, AppRoutes.settings.path);
      expect(find.text('Settings screen'), findsWidgets);
    });

    testWidgets('nested meals routes resolve within the shell', (tester) async {
      await pumpAt(tester, AppRoutes.mealsSearch.path);
      expect(find.text('Search recipes'), findsWidgets);

      await pumpAt(tester, AppRoutes.mealsImport.path);
      expect(find.text('Import recipe'), findsWidgets);

      await pumpAt(tester, AppRoutes.mealsDetailPath('42'));
      expect(find.text('Recipe 42'), findsOneWidget);
    });

    testWidgets('sign-in resolves outside the shell', (tester) async {
      // Signed-in users get bounced off /sign-in by design (see
      // auth_redirect_test.dart) — go signedOut here to test that the route
      // itself resolves, independent of that redirect policy.
      container
          .read(authStatusProvider.notifier)
          .setStatus(AuthStatus.signedOut);
      await pumpAt(tester, AppRoutes.signIn.path);
      expect(find.text('Sign in'), findsWidgets);
      expect(find.byType(NavigationBar), findsNothing);
    });

    testWidgets('intake routes resolve with no tab bar in the tree', (
      tester,
    ) async {
      await pumpAt(tester, AppRoutes.intakeManualEntry.path);
      expect(find.text('Add item'), findsWidgets);
      expect(
        find.byType(NavigationBar),
        findsNothing,
        reason:
            'AC-PAN-04: intake is a modal task, the tab bar must not be present',
      );

      await pumpAt(tester, AppRoutes.intakeDescribePantry.path);
      expect(find.text('Describe your shop'), findsWidgets);
      expect(find.byType(NavigationBar), findsNothing);

      await pumpAt(tester, AppRoutes.intakeDescribeShop.path);
      expect(find.text('Describe list'), findsWidgets);
      expect(find.byType(NavigationBar), findsNothing);
    });
  });
}
