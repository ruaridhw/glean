// Thumbs on cooked Plan rows: they replace the "Cooked?" pill once a meal is cooked, tapping the same
// thumb clears the rating, tapping the other switches it, and a long-press saves an optional note with it.
// Real router, real SQLite; the first-tap explainer is the only modal.
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/models/meal_thumb.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/router/app_routes.dart';

import '../../support/harness.dart';

void main() {
  late AppTestHarness h;
  final week = startOfWeek(DateTime.now());

  setUp(() {
    h = AppTestHarness();
  });
  tearDown(() => h.dispose());

  Future<int> plannedMeal(String title, {bool cooked = false}) async {
    final recipeId = await h.container
        .read(recipesRepositoryProvider)
        .save(
          userId: h.userId,
          title: title,
          ingredients: const <SaveRecipeIngredient>[],
        );
    final plan = h.container.read(planRepositoryProvider);
    final entryId = await plan.addEntry(
      userId: h.userId,
      recipeId: recipeId,
      recipeTitle: title,
      servings: 1,
      plannedDate: week,
    );
    if (cooked) {
      await plan.markCooked(
        entryId: entryId,
        userId: h.userId,
        now: DateTime.now().subtract(const Duration(hours: 2)),
      );
    }
    return entryId;
  }

  Future<MealPlanEntryView> readEntry(WidgetTester tester, int id) async {
    final entries = await tester.runAsync(
      () => h.container
          .read(planRepositoryProvider)
          .getWeek(userId: h.userId, weekStart: week),
    );
    return entries!.singleWhere((MealPlanEntryView entry) => entry.id == id);
  }

  Future<void> openPlan(WidgetTester tester) async {
    await h.pumpAt(tester, AppRoutes.plan.path);
    await tester.pumpAndSettle();
  }

  Future<void> rate(WidgetTester tester, String thumb) async {
    await tester.tap(find.byKey(Key('rating.$thumb')));
    await tester.pumpAndSettle();
    // The first thumb ever tapped opens the explainer; the rating is saved before it appears.
    if (find.text('How ratings work').evaluate().isNotEmpty) {
      await tester.tap(find.text('Got it'));
      await tester.pumpAndSettle();
    }
  }

  gleanWidgetTest('thumbs appear only on a cooked row, where the Cooked? pill '
      'was', (tester) async {
    await plannedMeal('Lentil Dal');
    await plannedMeal('Miso Soup', cooked: true);
    await openPlan(tester);

    expect(find.byKey(const Key('rating.up')), findsOneWidget);
    expect(find.byKey(const Key('rating.down')), findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, 'Cooked?'), findsOneWidget);

    await tester.tap(find.widgetWithText(OutlinedButton, 'Cooked?'));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('rating.up')), findsNWidgets(2));
    expect(find.byKey(const Key('rating.down')), findsNWidgets(2));
    expect(find.widgetWithText(OutlinedButton, 'Cooked?'), findsNothing);
  });

  gleanWidgetTest('tapping a thumb saves the rating, and tapping it again '
      'clears it', (tester) async {
    final entryId = await plannedMeal('Lentil Dal', cooked: true);
    await openPlan(tester);

    await rate(tester, 'up');
    expect((await readEntry(tester, entryId)).rating, MealThumb.up);

    await rate(tester, 'up');
    expect((await readEntry(tester, entryId)).rating, isNull);
  });

  gleanWidgetTest('tapping the other thumb switches the rating', (
    tester,
  ) async {
    final entryId = await plannedMeal('Lentil Dal', cooked: true);
    await openPlan(tester);

    await rate(tester, 'up');
    await rate(tester, 'down');

    expect((await readEntry(tester, entryId)).rating, MealThumb.down);
  });

  gleanWidgetTest('long-pressing a thumb saves the rating with its note', (
    tester,
  ) async {
    final entryId = await plannedMeal('Lentil Dal', cooked: true);
    await openPlan(tester);

    await tester.longPress(find.byKey(const Key('rating.down')));
    await tester.pumpAndSettle();
    expect(find.text('Thumbs down: Lentil Dal'), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('rating.note')),
      'too sweet for the kids',
    );
    await tester.tap(find.text('Save note'));
    await tester.pumpAndSettle();
    if (find.text('How ratings work').evaluate().isNotEmpty) {
      await tester.tap(find.text('Got it'));
      await tester.pumpAndSettle();
    }

    final entry = await readEntry(tester, entryId);
    expect(entry.rating, MealThumb.down);
    expect(entry.note, 'too sweet for the kids');
  });

  gleanWidgetTest('the note sheet opens with the saved note, and Skip leaves '
      'the entry alone', (tester) async {
    final entryId = await plannedMeal('Lentil Dal', cooked: true);
    final plan = h.container.read(planRepositoryProvider);
    await plan.rateWithNote(
      entryId: entryId,
      userId: h.userId,
      rating: MealThumb.up,
      note: 'a keeper',
    );
    await openPlan(tester);

    await tester.longPress(find.byKey(const Key('rating.up')));
    await tester.pumpAndSettle();
    expect(find.text('a keeper'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('rating.note')), 'changed');
    await tester.tap(find.text('Skip'));
    await tester.pumpAndSettle();

    final entry = await readEntry(tester, entryId);
    expect(entry.rating, MealThumb.up);
    expect(entry.note, 'a keeper');
  });

  gleanWidgetTest('each thumb is its own labelled button for a screen reader', (
    tester,
  ) async {
    final SemanticsHandle semantics = tester.ensureSemantics();
    await plannedMeal('Lentil Dal', cooked: true);
    await openPlan(tester);

    expect(find.bySemanticsLabel('Thumbs up'), findsOneWidget);
    expect(find.bySemanticsLabel('Thumbs down'), findsOneWidget);
    expect(
      tester.getSemantics(find.byKey(const Key('rating.up'))),
      matchesSemantics(
        label: 'Thumbs up',
        isButton: true,
        hasSelectedState: true,
        isFocusable: true,
        hasTapAction: true,
        hasLongPressAction: true,
        hasFocusAction: true,
      ),
    );
    semantics.dispose();
  });

  gleanWidgetTest('the explainer is shown on the first thumb ever tapped and '
      'never again', (tester) async {
    await plannedMeal('Lentil Dal', cooked: true);
    await openPlan(tester);

    await tester.tap(find.byKey(const Key('rating.up')));
    await tester.pumpAndSettle();
    expect(find.text('How ratings work'), findsOneWidget);
    expect(
      find.textContaining('Thumbs down stops the planner'),
      findsOneWidget,
    );
    expect(find.textContaining('Long-press a thumb'), findsOneWidget);
    await tester.tap(find.text('Got it'));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('rating.down')));
    await tester.pumpAndSettle();
    expect(find.text('How ratings work'), findsNothing);
  });
}
