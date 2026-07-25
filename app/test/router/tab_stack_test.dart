// Each tab keeps its own independent navigation stack (the direct analogue
// of the RN app's per-tab `Stack` navigators): a push in one tab survives
// switching to another tab and back — StatefulShellRoute.indexedStack's
// whole reason for existing.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/router.dart';

/// Taps a `NavigationBar` destination by its label, not by coordinates —
/// resilient to layout and avoids matching a same-named `Text` elsewhere on
/// screen (e.g. an `AppBar` title).
Future<void> tapTab(WidgetTester tester, String label) async {
  final finder = find.descendant(
    of: find.byType(NavigationBar),
    matching: find.text(label),
  );
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('pushing in Meals survives switching tabs and back', (
    tester,
  ) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final router = container.read(goRouterProvider);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Pantry screen'), findsWidgets);

    await tapTab(tester, 'Meals');
    expect(find.text('Meals screen'), findsWidgets);

    // Placeholders have no real navigation actions yet (Wave 3's job) —
    // push directly through the router, same as a feature screen would.
    unawaited(router.push(AppRoutes.mealsSearch.path));
    await tester.pumpAndSettle();
    expect(find.text('Search recipes'), findsWidgets);

    await tapTab(tester, 'Pantry');
    expect(find.text('Pantry screen'), findsWidgets);
    expect(find.text('Search recipes'), findsNothing);

    await tapTab(tester, 'Meals');
    expect(
      find.text('Search recipes'),
      findsWidgets,
      reason:
          'Meals branch must restore exactly where it was left, not reset to its home route',
    );
  });

  testWidgets('tapping the active tab again resets its own stack', (
    tester,
  ) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final router = container.read(goRouterProvider);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    await tapTab(tester, 'Meals');
    unawaited(router.push(AppRoutes.mealsSearch.path));
    await tester.pumpAndSettle();
    expect(find.text('Search recipes'), findsWidgets);

    // Tapping the currently-active tab is the RN app's "tap the tab you're
    // already on" reset gesture — it should collapse back to that branch's
    // home route.
    await tapTab(tester, 'Meals');
    expect(find.text('Meals screen'), findsWidgets);
    expect(find.text('Search recipes'), findsNothing);
  });
}
