// Real router/SQLite coverage. Failures occur at SQLite, not repository mocks.
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/router/app_routes.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import '../../support/harness.dart';

void main() {
  late AppTestHarness h;
  final week = startOfWeek(DateTime.now());
  setUp(() => h = AppTestHarness());
  tearDown(() => h.dispose());
  Future<int> dinner(
    String title, {
    DateTime? date,
    bool ingredient = false,
  }) async {
    final r = await h.container
        .read(recipesRepositoryProvider)
        .save(
          userId: h.userId,
          title: title,
          ingredients: ingredient
              ? [
                  const SaveRecipeIngredient(
                    canonicalName: 'chicken breast',
                    quantity: 100,
                    unit: 'g',
                  ),
                ]
              : const [],
        );
    return h.container
        .read(planRepositoryProvider)
        .addEntry(
          userId: h.userId,
          recipeId: r,
          recipeTitle: title,
          servings: 1,
          plannedDate: date ?? week,
        );
  }

  Future<void> capacity(int n) => h.container
      .read(userConfigRepositoryProvider)
      .save(
        UserConfigView(
          id: h.userId,
          purchaseTolerance: 0.5,
          preferredServings: 1,
          mealsPerWeek: n,
          dietaryFlags: const [],
          maxActiveTimeMins: null,
        ),
      );
  Future<void> open(WidgetTester tester) async {
    await h.pumpAt(tester, AppRoutes.plan.path);
    await tester.pumpAndSettle();
  }

  Future<void> stock() => h.container
      .read(pantryRepositoryProvider)
      .addItem(
        userId: h.userId,
        name: 'chicken breast',
        quantity: 500,
        unit: 'g',
        category: 'poultry',
      );
  Future<void> tab(WidgetTester tester, String label) async {
    await tester.tap(
      find.descendant(
        of: find.byType(NavigationBar),
        matching: find.text(label),
      ),
    );
    await tester.pumpAndSettle();
  }

  gleanWidgetTest('week pagination displays only entries in the viewed week', (
    tester,
  ) async {
    await dinner('Today');
    await dinner('Next dinner', date: week.add(const Duration(days: 7)));
    await open(tester);
    expect(find.text('Today'), findsOneWidget);
    expect(find.text('Next dinner'), findsNothing);
    await tester.tap(find.byTooltip('Next week'));
    await tester.pumpAndSettle();
    expect(find.text('Next dinner'), findsOneWidget);
    expect(find.text('Today'), findsNothing);
    await tester.tap(find.byTooltip('Previous week'));
    await tester.pumpAndSettle();
    expect(find.text('Today'), findsOneWidget);
  });
  gleanWidgetTest('cooked meals stay visible but free capacity', (
    tester,
  ) async {
    await capacity(1);
    final id = await dinner('Cooked dinner');
    await h.container
        .read(planRepositoryProvider)
        .markCooked(entryId: id, userId: h.userId);
    await open(tester);
    expect(find.text('Cooked dinner'), findsOneWidget);
    expect(find.text('Add a dinner'), findsOneWidget);
  });
  gleanWidgetTest('capacity belongs to the paged week, not the lifetime plan', (
    tester,
  ) async {
    await capacity(1);
    await dinner('Current dinner');
    await open(tester);
    expect(find.text('Add a dinner'), findsNothing);
    await tester.tap(find.byTooltip('Next week'));
    await tester.pumpAndSettle();
    expect(find.text('Add a dinner'), findsOneWidget);
  });
  gleanWidgetTest(
    'rollover on load retains entry identity and is not repeated on refocus',
    (tester) async {
      final id = await dinner(
        'Old dinner',
        date: week.subtract(const Duration(days: 7)),
      );
      await open(tester);
      expect(find.text('Old dinner'), findsOneWidget);
      await tab(tester, 'Pantry');
      await tab(tester, 'Plan');
      final entries = await tester.runAsync(
        () => h.container
            .read(planRepositoryProvider)
            .getWeek(userId: h.userId, weekStart: week),
      );
      expect(entries!.single.id, id);
    },
  );
  gleanWidgetTest(
    'manually adding a real recipe then refocusing Plan never re-adds it',
    (tester) async {
      final r = await h.container
          .read(recipesRepositoryProvider)
          .save(userId: h.userId, title: 'Added dinner', ingredients: const []);
      await h.pumpAt(tester, AppRoutes.mealsDetailPath('$r'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Add to plan'));
      await tester.pumpAndSettle();
      await tab(tester, 'Plan');
      await tab(tester, 'Meals');
      await tab(tester, 'Plan');
      expect(
        await tester.runAsync(
          () => h.container
              .read(planRepositoryProvider)
              .getWeek(userId: h.userId, weekStart: week),
        ),
        hasLength(1),
      );
      expect(find.text('Added dinner'), findsOneWidget);
    },
  );
  gleanWidgetTest('an empty slot opens Meals with one light acknowledgement', (
    tester,
  ) async {
    await capacity(1);
    await open(tester);
    await tester.tap(find.text('Add a dinner'));
    await tester.pumpAndSettle();
    expect(
      h.router.routeInformationProvider.value.uri.path,
      AppRoutes.meals.path,
    );
  });
  gleanWidgetTest(
    'deletion Undo restores the exact entry and its shopping demand',
    (tester) async {
      final id = await dinner('Curry', ingredient: true);
      final plan = h.container.read(planRepositoryProvider);
      final entry = (await plan.getWeek(
        userId: h.userId,
        weekStart: week,
      )).single;
      final shop = h.container.read(shoppingRepositoryProvider);
      await shop.addGapsForRecipe(
        userId: h.userId,
        recipeId: entry.recipeId!,
        servings: 1,
        sourceMealPlanEntryId: id,
      );
      await open(tester);
      await tester.drag(find.text('Curry'), const Offset(-600, 0));
      await tester.pumpAndSettle();
      expect(
        await tester.runAsync(() => shop.watchAll(h.userId).first),
        isEmpty,
      );
      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();
      expect(
        (await tester.runAsync(
          () => plan.getWeek(userId: h.userId, weekStart: week),
        ))!.single.id,
        id,
      );
      expect(
        (await tester.runAsync(
          () => shop.watchAll(h.userId).first,
        ))!.single.quantity,
        100,
      );
    },
  );
  gleanWidgetTest(
    'a real SQLite deletion failure is surfaced and leaves the entry intact',
    (tester) async {
      await dinner('Curry');
      await h.db.customStatement(
        "CREATE TRIGGER fail_delete BEFORE DELETE ON meal_plan_entries BEGIN SELECT RAISE(ABORT, 'test failure'); END",
      );
      await open(tester);
      await tester.drag(find.text('Curry'), const Offset(-600, 0));
      await tester.pumpAndSettle();
      expect(find.textContaining('Could not remove'), findsOneWidget);
      expect(
        await tester.runAsync(
          () => h.container
              .read(planRepositoryProvider)
              .getWeek(userId: h.userId, weekStart: week),
        ),
        hasLength(1),
      );
      expect(tester.takeException(), isNull);
    },
  );
  gleanWidgetTest(
    'a real SQLite cook failure rolls stock back and leaves the meal uncooked',
    (tester) async {
      await stock();
      await dinner('Curry', ingredient: true);
      await h.db.customStatement(
        "CREATE TRIGGER fail_cook BEFORE UPDATE ON meal_plan_entries WHEN NEW.cooked_at IS NOT NULL BEGIN SELECT RAISE(ABORT, 'test failure'); END",
      );
      await open(tester);
      await tester.tap(find.widgetWithText(OutlinedButton, 'Cooked?'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Could not mark'), findsOneWidget);
      expect(
        (await tester.runAsync(
          () => h.container.read(pantryRepositoryProvider).getAll(h.userId),
        ))!.single.quantity,
        500,
      );
      expect(find.widgetWithText(OutlinedButton, 'Cooked?'), findsOneWidget);
    },
  );
  gleanWidgetTest(
    'a real SQLite Undo cooking failure cannot half-restore stock',
    (tester) async {
      await stock();
      await dinner('Curry', ingredient: true);
      await open(tester);
      await tester.tap(find.widgetWithText(OutlinedButton, 'Cooked?'));
      await tester.pumpAndSettle();
      await tester.runAsync(
        () => h.db.customStatement(
          "CREATE TRIGGER fail_undo BEFORE DELETE ON cooked_adjustments BEGIN SELECT RAISE(ABORT, 'test failure'); END",
        ),
      );
      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Could not undo cooking'), findsOneWidget);
      expect(
        (await tester.runAsync(
          () => h.container.read(pantryRepositoryProvider).getAll(h.userId),
        ))!.single.quantity,
        400,
      );
    },
  );
  gleanWidgetTest(
    'cooking and Undo visibly reverse the exact pantry quantity',
    (tester) async {
      await stock();
      await dinner('Curry', ingredient: true);
      await open(tester);
      await tester.tap(find.widgetWithText(OutlinedButton, 'Cooked?'));
      await tester.pumpAndSettle();
      expect(find.widgetWithText(OutlinedButton, 'Cooked?'), findsNothing);
      expect(
        (await tester.runAsync(
          () => h.container.read(pantryRepositoryProvider).getAll(h.userId),
        ))!.single.quantity,
        400,
      );
      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();
      expect(find.widgetWithText(OutlinedButton, 'Cooked?'), findsOneWidget);
      expect(
        (await tester.runAsync(
          () => h.container.read(pantryRepositoryProvider).getAll(h.userId),
        ))!.single.quantity,
        500,
      );
    },
  );
  gleanWidgetTest(
    'Generate is inert while its actual HTTP request is pending',
    (tester) async {
      await h.dispose();
      final response = Completer<http.Response>();
      var requests = 0;
      h = AppTestHarness(
        httpClient: MockClient((_) {
          requests++;
          return response.future;
        }),
      );
      await open(tester);
      await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
      await tester.pump();
      expect(find.text('Generating'), findsOneWidget);
      response.complete(http.Response('{"suggestions":[]}', 200));
      await tester.pumpAndSettle();
      expect(requests, 1);
      expect(find.text('No recipes fit right now. Try again.'), findsOneWidget);
    },
  );
}
