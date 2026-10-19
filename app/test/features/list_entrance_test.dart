// Pantry, Shop and Meals rows fade in when they are inserted. A row that was
// already on screen keeps its state and does not replay the entrance, because
// each row's entrance is keyed by its database id.
import 'package:flutter/widgets.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/router/app_routes.dart';

import '../support/harness.dart';

Finder _entrance(String label) =>
    find.ancestor(of: find.text(label), matching: find.byType(Animate));

/// The entrance opacity of the row showing [label]: the outermost
/// `FadeTransition` inside its [Animate].
double _entranceOpacity(WidgetTester tester, String label) {
  expect(
    _entrance(label),
    findsOneWidget,
    reason: '"$label" has no entrance animation',
  );
  final FadeTransition fade = tester.widget<FadeTransition>(
    find
        .descendant(of: _entrance(label), matching: find.byType(FadeTransition))
        .first,
  );
  return fade.opacity.value;
}

/// Pumps [location] with [existing] already listed, runs [insert] through the
/// real repository, and checks that only the inserted row animates. Each
/// [insert] puts its row above [existing], so a key on the wrong widget would
/// hand [existing]'s element to the new row and replay [existing]'s entrance.
Future<void> _expectOnlyInsertedRowAnimates(
  WidgetTester tester, {
  required AppTestHarness harness,
  required String location,
  required String existing,
  required String inserted,
  required Future<void> Function() insert,
}) async {
  await harness.pumpAt(tester, location);
  await tester.pumpAndSettle();
  expect(_entranceOpacity(tester, existing), 1);
  final State<StatefulWidget> before = tester.state(_entrance(existing));

  await insert();
  // Zero-duration pumps until the stream delivers the new row, so no
  // animation time passes before the first frame that shows it.
  for (int i = 0; i < 10 && find.text(inserted).evaluate().isEmpty; i++) {
    await tester.pump();
  }

  expect(_entranceOpacity(tester, inserted), lessThan(1));
  expect(_entranceOpacity(tester, existing), 1);
  expect(
    tester.state(_entrance(existing)),
    same(before),
    reason: 'the existing row must keep its element, not replay its entrance',
  );

  await tester.pumpAndSettle();
  expect(find.text(existing), findsOneWidget);
  expect(find.text(inserted), findsOneWidget);
  expect(_entranceOpacity(tester, inserted), 1);
  expect(
    tester.getTopLeft(find.text(inserted)).dy,
    lessThan(tester.getTopLeft(find.text(existing)).dy),
  );
}

void main() {
  gleanWidgetTest('Pantry: only an inserted row fades in', (
    WidgetTester tester,
  ) async {
    final AppTestHarness harness = AppTestHarness();
    addTearDown(harness.dispose);
    Future<int> addMilk(String name, DateTime now) => harness.container
        .read(pantryRepositoryProvider)
        .addItem(
          userId: harness.userId,
          name: name,
          quantity: 1,
          unit: 'l',
          groupId: 'dairy',
          now: now,
        );
    await addMilk('whole milk', DateTime(2026, 1, 1));

    await _expectOnlyInsertedRowAnimates(
      tester,
      harness: harness,
      location: AppRoutes.pantry.path,
      existing: 'whole milk',
      inserted: 'oat milk',
      // An earlier purchase expires sooner, so it sorts above.
      insert: () => addMilk('oat milk', DateTime(2025, 12, 1)),
    );
  });

  gleanWidgetTest('Shop: only an inserted row fades in', (
    WidgetTester tester,
  ) async {
    final AppTestHarness harness = AppTestHarness();
    addTearDown(harness.dispose);
    Future<int> add(String name) => harness.container
        .read(shoppingRepositoryProvider)
        .addManualItem(userId: harness.userId, name: name);
    await add('Bananas');

    await _expectOnlyInsertedRowAnimates(
      tester,
      harness: harness,
      location: AppRoutes.shop.path,
      existing: 'Bananas',
      inserted: 'Apples',
      insert: () => add('Apples'),
    );
  });

  gleanWidgetTest('Meals: only an inserted saved recipe fades in', (
    WidgetTester tester,
  ) async {
    final AppTestHarness harness = AppTestHarness();
    addTearDown(harness.dispose);
    Future<int> save(String title) => harness.container
        .read(recipesRepositoryProvider)
        .save(
          userId: harness.userId,
          title: title,
          ingredients: const <SaveRecipeIngredient>[],
        );
    await save('Chicken Curry');

    await _expectOnlyInsertedRowAnimates(
      tester,
      harness: harness,
      location: AppRoutes.meals.path,
      existing: 'Chicken Curry',
      inserted: 'Lentil Soup',
      insert: () => save('Lentil Soup'),
    );
  });
}
