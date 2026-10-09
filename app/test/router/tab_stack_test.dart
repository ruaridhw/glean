// Each tab keeps its own independent navigation stack (the direct analogue
// of the RN app's per-tab `Stack` navigators): a push in one tab survives
// switching to another tab and back — StatefulShellRoute.indexedStack's
// whole reason for existing.
//
// Assertions are on screen *widget type*, not copy — Meals already has a
// real screen; Pantry doesn't yet, but must not matter to this test either
// way. Uses the `import` nested route as the vehicle for exercising the
// stack (search was dropped — AC-MEAL-07, there is no dedicated route for
// it any more).

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/features/meals/meals_import_screen.dart';
import 'package:glean/features/meals/meals_screen.dart';
import 'package:glean/features/pantry/pantry_screen.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';

import '../support/harness.dart';

/// Taps a `NavigationBar` destination by its label, not by coordinates —
/// resilient to layout and avoids matching a same-named `Text` elsewhere on
/// screen (e.g. an `AppBar` title). The label itself is `AppShell`'s own
/// copy (router-owned), not a feature placeholder, so it's stable to assert
/// against.
Future<void> tapTab(WidgetTester tester, String label) async {
  final finder = find.descendant(
    of: find.byType(NavigationBar),
    matching: find.text(label),
  );
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

void main() {
  late AppTestHarness harness;

  setUp(() {
    harness = AppTestHarness();
  });

  tearDown(() => harness.dispose());

  testWidgets('every tab tap fires the selection haptic (AC-HAP-05)', (
    tester,
  ) async {
    await tester.pumpWidget(harness.app());
    await tester.pumpAndSettle();
    harness.hapticCalls.clear();

    await tapTab(tester, 'Meals');
    await tapTab(tester, 'Meals');

    expect(harness.hapticCalls, <HapticWeight>[
      HapticWeight.selection,
      HapticWeight.selection,
    ]);
  });

  testWidgets('pushing in Meals survives switching tabs and back', (
    tester,
  ) async {
    await tester.pumpWidget(harness.app());
    await tester.pumpAndSettle();
    expect(find.byType(PantryScreen), findsOneWidget);

    await tapTab(tester, 'Meals');
    expect(find.byType(MealsScreen), findsOneWidget);

    // Push directly through the router rather than tapping a real
    // navigation affordance — this suite tests routing, not any particular
    // feature's UI for reaching that route.
    unawaited(harness.router.push(AppRoutes.mealsImport.path));
    await tester.pumpAndSettle();
    expect(find.byType(MealsImportScreen), findsOneWidget);

    await tapTab(tester, 'Pantry');
    expect(find.byType(PantryScreen), findsOneWidget);
    expect(find.byType(MealsImportScreen), findsNothing);

    await tapTab(tester, 'Meals');
    expect(
      find.byType(MealsImportScreen),
      findsOneWidget,
      reason:
          'Meals branch must restore exactly where it was left, not reset to its home route',
    );
  });

  testWidgets('tapping the active tab again resets its own stack', (
    tester,
  ) async {
    await tester.pumpWidget(harness.app());
    await tester.pumpAndSettle();

    await tapTab(tester, 'Meals');
    unawaited(harness.router.push(AppRoutes.mealsImport.path));
    await tester.pumpAndSettle();
    expect(find.byType(MealsImportScreen), findsOneWidget);

    // Tapping the currently-active tab is the RN app's "tap the tab you're
    // already on" reset gesture — it should collapse back to that branch's
    // home route.
    await tapTab(tester, 'Meals');
    expect(find.byType(MealsScreen), findsOneWidget);
    expect(find.byType(MealsImportScreen), findsNothing);
  });
}
