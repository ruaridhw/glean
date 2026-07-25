// Route-table structure (AC-TEST-14): the five tab branches exist, every
// route resolves to real content, names are unique, and the intake flow
// resolves outside the tab shell (no `NavigationBar` while it's active).
//
// Assertions here are structural (which screen *class* is mounted, whether
// a `NavigationBar` is present) rather than textual — feature waves replace
// placeholder copy wholesale, and routing correctness must not depend on it.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/features/auth/sign_in_screen.dart';
import 'package:glean/features/intake/manual_entry_screen.dart';
import 'package:glean/features/intake/pantry_describe_screen.dart';
import 'package:glean/features/intake/shop_describe_screen.dart';
import 'package:glean/features/meals/meal_detail_screen.dart';
import 'package:glean/features/meals/meals_import_screen.dart';
import 'package:glean/features/meals/meals_screen.dart';
import 'package:glean/features/meals/meals_search_screen.dart';
import 'package:glean/features/pantry/pantry_screen.dart';
import 'package:glean/features/plan/plan_screen.dart';
import 'package:glean/features/settings/settings_screen.dart';
import 'package:glean/features/shop/shop_screen.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/auth_state.dart';

import '../support/harness.dart';

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
    late AppTestHarness harness;

    setUp(() {
      harness = AppTestHarness();
    });

    tearDown(() => harness.dispose());

    Future<void> pumpAt(WidgetTester tester, String location) async {
      await harness.pumpAt(tester, location);
      await tester.pumpAndSettle();
    }

    testWidgets('each tab branch root resolves to its own screen widget', (
      tester,
    ) async {
      await pumpAt(tester, AppRoutes.pantry.path);
      expect(find.byType(PantryScreen), findsOneWidget);

      await pumpAt(tester, AppRoutes.meals.path);
      expect(find.byType(MealsScreen), findsOneWidget);

      await pumpAt(tester, AppRoutes.plan.path);
      expect(find.byType(PlanScreen), findsOneWidget);

      await pumpAt(tester, AppRoutes.shop.path);
      expect(find.byType(ShopScreen), findsOneWidget);

      await pumpAt(tester, AppRoutes.settings.path);
      expect(find.byType(SettingsScreen), findsOneWidget);
    });

    testWidgets('nested meals routes resolve within the shell', (tester) async {
      await pumpAt(tester, AppRoutes.mealsSearch.path);
      expect(find.byType(MealsSearchScreen), findsOneWidget);

      await pumpAt(tester, AppRoutes.mealsImport.path);
      expect(find.byType(MealsImportScreen), findsOneWidget);

      // A syntactically-valid id must reach the screen — whether that
      // specific recipe exists in the database is a data/feature concern,
      // not routing's. See error_handling_test.dart for the format guard
      // that *does* belong to routing (a non-numeric id never gets here).
      await pumpAt(tester, AppRoutes.mealsDetailPath('42'));
      expect(find.byType(MealDetailScreen), findsOneWidget);
    });

    testWidgets('sign-in resolves outside the shell', (tester) async {
      // Signed-in users get bounced off /sign-in by design (see
      // auth_redirect_test.dart) — go signedOut here to test that the route
      // itself resolves, independent of that redirect policy.
      harness.container
          .read(authStatusProvider.notifier)
          .setStatus(AuthStatus.signedOut);
      await pumpAt(tester, AppRoutes.signIn.path);
      expect(find.byType(SignInScreen), findsOneWidget);
      expect(find.byType(NavigationBar), findsNothing);
    });

    testWidgets('intake routes resolve with no tab bar in the tree', (
      tester,
    ) async {
      await pumpAt(tester, AppRoutes.intakeManualEntry.path);
      expect(find.byType(ManualEntryScreen), findsOneWidget);
      expect(
        find.byType(NavigationBar),
        findsNothing,
        reason:
            'AC-PAN-04: intake is a modal task, the tab bar must not be present',
      );

      await pumpAt(tester, AppRoutes.intakeDescribePantry.path);
      expect(find.byType(PantryDescribeScreen), findsOneWidget);
      expect(find.byType(NavigationBar), findsNothing);

      await pumpAt(tester, AppRoutes.intakeDescribeShop.path);
      expect(find.byType(ShopDescribeScreen), findsOneWidget);
      expect(find.byType(NavigationBar), findsNothing);
    });
  });
}
