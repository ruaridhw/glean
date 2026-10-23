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

  gleanWidgetTest(
    'the note sheet fits a 320px phone at 2x text with the keyboard up',
    (tester) async {
      // 320x640, doubled text and a 300px keyboard: the layout the sheet overflowed by 156px across and
      // 270px down before it scrolled.
      tester.view.physicalSize = const Size(320, 640);
      tester.view.devicePixelRatio = 1;
      tester.platformDispatcher.textScaleFactorTestValue = 2;
      addTearDown(tester.view.reset);
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);

      final int entryId = await plannedMeal('Lentil Dal', cooked: true);
      await openPlan(tester);
      // Large text pushes the first row below the fold, so scroll to it as a person would.
      await tester.scrollUntilVisible(
        find.byKey(const Key('rating.down')),
        200,
      );
      await tester.ensureVisible(find.byKey(const Key('rating.down')));
      await tester.pumpAndSettle();
      await tester.longPress(find.byKey(const Key('rating.down')));
      await tester.pumpAndSettle();
      // The keyboard the field's autofocus brings up, which pushes the sheet into the space that is left.
      tester.view.viewInsets = const FakeViewPadding(bottom: 300);
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Save note'), findsOneWidget);
      expect(
        tester.getRect(find.text('Save note')).bottom,
        lessThanOrEqualTo(640 - 300),
        reason: 'the actions stay above the keyboard, not scrolled away',
      );

      await tester.enterText(find.byKey(const Key('rating.note')), 'too sweet');
      await tester.tap(find.text('Save note'));
      await tester.pumpAndSettle();
      if (find.text('How ratings work').evaluate().isNotEmpty) {
        await tester.tap(find.text('Got it'));
        await tester.pumpAndSettle();
      }

      final MealPlanEntryView entry = await readEntry(tester, entryId);
      expect(entry.rating, MealThumb.down);
      expect(entry.note, 'too sweet');
    },
  );

  gleanWidgetTest(
    'the note sheet fits a 320px phone at 1.3x text without a keyboard',
    (tester) async {
      tester.view.physicalSize = const Size(320, 640);
      tester.view.devicePixelRatio = 1;
      tester.platformDispatcher.textScaleFactorTestValue = 1.3;
      addTearDown(tester.view.reset);
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);

      await plannedMeal('Lentil Dal', cooked: true);
      await openPlan(tester);
      await tester.scrollUntilVisible(
        find.byKey(const Key('rating.up')),
        200,
      );
      await tester.ensureVisible(find.byKey(const Key('rating.up')));
      await tester.pumpAndSettle();
      await tester.longPress(find.byKey(const Key('rating.up')));
      await tester.pumpAndSettle();
      tester.view.viewInsets = const FakeViewPadding(bottom: 300);
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Save note'), findsOneWidget);
      expect(find.text('Skip'), findsOneWidget);
      expect(
        tester.getRect(find.text('Save note')).bottom,
        lessThanOrEqualTo(340),
      );
    },
  );

  gleanWidgetTest('the note field counts code points, so a combining note that '
      'saves still passes the backend bound', (tester) async {
    final int entryId = await plannedMeal('Lentil Dal', cooked: true);
    await openPlan(tester);
    await tester.longPress(find.byKey(const Key('rating.down')));
    await tester.pumpAndSettle();

    // 300 visible characters written as e + combining acute: 600 code points, which Flutter's own
    // grapheme-based maxLength would have let through and the backend would have refused.
    final String combining = 'e\u0301' * 300;
    await tester.enterText(find.byKey(const Key('rating.note')), combining);
    await tester.pumpAndSettle();

    final String shown = tester
        .widget<TextField>(find.byKey(const Key('rating.note')))
        .controller!
        .text;
    expect(ratingNoteLength(shown), lessThanOrEqualTo(maxRatingNoteLength));
    expect(find.text('${ratingNoteLength(shown)}/$maxRatingNoteLength'), findsOneWidget);

    await tester.tap(find.text('Save note'));
    await tester.pumpAndSettle();
    if (find.text('How ratings work').evaluate().isNotEmpty) {
      await tester.tap(find.text('Got it'));
      await tester.pumpAndSettle();
    }

    final String? saved = (await readEntry(tester, entryId)).note;
    expect(saved, isNotNull);
    expect(ratingNoteLength(saved!), lessThanOrEqualTo(maxRatingNoteLength));
    // Nothing half-written: the kept text is a whole number of e + combining-acute clusters.
    expect(saved.characters.every((String c) => c == 'e\u0301'), isTrue);
  });

  gleanWidgetTest('two thumbs tapped in the same frame open one explainer, and '
      'one note sheet at a time', (tester) async {
    await plannedMeal('Lentil Dal', cooked: true);
    await openPlan(tester);

    // No settle between the taps: both first-tap paths run before either has answered its claim.
    await tester.tap(find.byKey(const Key('rating.up')));
    await tester.tap(find.byKey(const Key('rating.down')));
    await tester.pumpAndSettle();

    expect(
      find.text('How ratings work', skipOffstage: false),
      findsOneWidget,
      reason: 'a second copy must not be stacked under the first',
    );
  });

  gleanWidgetTest('a long title wraps to two lines and never shrinks the thumbs',
      (tester) async {
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    const String title = 'Lemon and herb salmon traybake with crushed potatoes';
    await plannedMeal(title, cooked: true);
    await openPlan(tester);
    await tester.scrollUntilVisible(find.text(title), 200);

    expect(tester.takeException(), isNull);
    expect(tester.widget<Text>(find.text(title)).maxLines, 2);
    expect(tester.getSize(find.byKey(const Key('rating.up'))), const Size(44, 44));
    expect(
      tester.getSize(find.byKey(const Key('rating.down'))),
      const Size(44, 44),
    );
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
