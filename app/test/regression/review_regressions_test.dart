import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/features/plan/providers/generate_week_controller.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';
import '../support/harness.dart';

class MHttp extends Mock implements http.Client {}

void main() {
  setUpAll(() => registerFallbackValue(Uri.parse('http://localhost/')));
  final week = startOfWeek(DateTime.now());
  Future<int> recipe(AppTestHarness h, String title, double qty, String unit) =>
      h.container
          .read(recipesRepositoryProvider)
          .save(
            userId: h.userId,
            title: title,
            ingredients: [
              SaveRecipeIngredient(
                canonicalName: 'chicken breast',
                quantity: qty,
                unit: unit,
              ),
            ],
          );
  gleanWidgetTest(
    'a pending cook can finish after its route is disposed without using a dead widget ref',
    (tester) async {
      final h = AppTestHarness();
      addTearDown(h.dispose);
      final id = await recipe(h, 'Slow dinner', 100, 'g');
      final plan = h.container.read(planRepositoryProvider);
      await plan.addEntry(
        userId: h.userId,
        recipeId: id,
        recipeTitle: 'Slow dinner',
        servings: 1,
      );
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      final entered = Completer<void>();
      final release = Completer<void>();
      final held = h.db.transaction(() async {
        entered.complete();
        await release.future;
      });
      await entered.future;
      await tester.tap(find.text('Cooked?'));
      await tester.pump();
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.runAsync(() async {
        release.complete();
        await held;
      });
      final entries = await tester.runAsync(
        () => plan.getWeek(userId: h.userId, weekStart: week),
      );
      await tester.pump();
      expect(entries!.single.isCooked, isTrue);
      expect(tester.takeException(), isNull);
    },
  );

  test(
    'undo cooking restores recipe history without clobbering a later cook',
    () async {
      final h = AppTestHarness();
      addTearDown(h.dispose);
      final pantry = h.container.read(pantryRepositoryProvider);
      await pantry.addItem(
        userId: h.userId,
        name: 'chicken breast',
        quantity: 500,
        unit: 'g',
        category: 'poultry',
      );
      final r = await recipe(h, 'Repeat dinner', 50, 'g');
      final plan = h.container.read(planRepositoryProvider);
      final a = await plan.addEntry(
        userId: h.userId,
        recipeId: r,
        recipeTitle: 'Repeat dinner',
        servings: 1,
      );
      final b = await plan.addEntry(
        userId: h.userId,
        recipeId: r,
        recipeTitle: 'Repeat dinner',
        servings: 1,
      );
      final t1 = DateTime(2026, 1, 1);
      final t2 = DateTime(2026, 1, 2);
      await plan.markCooked(entryId: a, userId: h.userId, now: t1);
      await plan.markCooked(entryId: b, userId: h.userId, now: t2);
      await plan.undoCooked(entryId: a, userId: h.userId);
      final recipes = h.container.read(recipesRepositoryProvider);
      expect(
        (await recipes.getById(id: r, userId: h.userId))!.lastCookedAt,
        t2,
      );
      await plan.undoCooked(entryId: b, userId: h.userId);
      expect(
        (await recipes.getById(id: r, userId: h.userId))!.lastCookedAt,
        isNull,
      );
      expect((await pantry.getAll(h.userId)).single.quantity, 500);
    },
  );

  test(
    'Generate excludes a planned corpus identity even after library deletion',
    () async {
      final client = MHttp();
      final h = AppTestHarness(httpClient: client);
      addTearDown(h.dispose);
      final recipes = h.container.read(recipesRepositoryProvider);
      final r = await recipes.save(
        userId: h.userId,
        externalId: 'rec_keep',
        title: 'Deleted dinner',
        ingredients: const [],
      );
      await h.container
          .read(planRepositoryProvider)
          .addEntry(
            userId: h.userId,
            recipeId: r,
            recipeTitle: 'Deleted dinner',
            servings: 1,
          );
      await recipes.deleteRecipe(id: r, userId: h.userId);
      Map<String, dynamic>? payload;
      when(
        () => client.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer((call) async {
        payload =
            jsonDecode(call.namedArguments[#body] as String)
                as Map<String, dynamic>;
        return http.Response('{"suggestions":[]}', 200);
      });
      await h.container
          .read(generateWeekControllerProvider.notifier)
          .generate(weekStart: week, slots: 2, servings: 1);
      expect(payload!['exclude_external_ids'], contains('rec_keep'));
    },
  );

  test(
    'when pantry and recipe units differ then shopping gaps use equivalent quantities',
    () async {
      final h = AppTestHarness();
      addTearDown(h.dispose);
      await h.container
          .read(pantryRepositoryProvider)
          .addItem(
            userId: h.userId,
            name: 'chicken breast',
            quantity: 200,
            unit: 'g',
            category: 'poultry',
          );
      final r = await recipe(h, 'Dinner', 0.3, 'kg');
      final p = h.container.read(planRepositoryProvider);
      final e = await p.addEntry(
        userId: h.userId,
        recipeId: r,
        recipeTitle: 'Dinner',
        servings: 1,
      );
      await h.container
          .read(shoppingRepositoryProvider)
          .addGapsForRecipe(
            userId: h.userId,
            recipeId: r,
            servings: 1,
            sourceMealPlanEntryId: e,
          );
      final gaps = await h.container
          .read(shoppingRepositoryProvider)
          .watchAll(h.userId)
          .first;
      expect(
        gaps,
        hasLength(1),
        reason: '300g needed, 200g owned: 100g still missing',
      );
      expect(gaps.single.quantity, 100);
      expect(gaps.single.unit, 'g');
    },
  );
  for (final operation in ['delete', 'cook']) {
    test(
      'shared meals allocate stock once and recompute demand after $operation',
      () async {
        final h = AppTestHarness();
        addTearDown(h.dispose);
        final pantry = h.container.read(pantryRepositoryProvider);
        await pantry.addItem(
          userId: h.userId,
          name: 'chicken breast',
          quantity: 200,
          unit: 'g',
          category: 'poultry',
        );
        final plan = h.container.read(planRepositoryProvider);
        final shop = h.container.read(shoppingRepositoryProvider);
        final ids = <int>[];
        for (final title in ['A', 'B']) {
          final r = await recipe(h, title, 200, 'g');
          final id = await plan.addEntry(
            userId: h.userId,
            recipeId: r,
            recipeTitle: title,
            servings: 1,
          );
          ids.add(id);
          await shop.addGapsForRecipe(
            userId: h.userId,
            recipeId: r,
            servings: 1,
            sourceMealPlanEntryId: id,
          );
        }
        expect((await shop.watchAll(h.userId).first).single.quantity, 200);
        if (operation == 'delete') {
          await plan.deleteEntry(id: ids.first, userId: h.userId);
        } else {
          await plan.markCooked(entryId: ids.first, userId: h.userId);
        }
        final remaining = await shop.watchAll(h.userId).first;
        if (operation == 'delete') {
          expect(remaining, isEmpty);
        } else {
          expect(remaining.single.quantity, 200);
        }
      },
    );
  }

  test(
    'when one of two meals needing chicken is deleted then the other shopping requirement survives',
    () async {
      final h = AppTestHarness();
      addTearDown(h.dispose);
      final p = h.container.read(planRepositoryProvider);
      final s = h.container.read(shoppingRepositoryProvider);
      for (final title in ['A', 'B']) {
        final r = await recipe(h, title, 200, 'g');
        final e = await p.addEntry(
          userId: h.userId,
          recipeId: r,
          recipeTitle: title,
          servings: 1,
        );
        await s.addGapsForRecipe(
          userId: h.userId,
          recipeId: r,
          servings: 1,
          sourceMealPlanEntryId: e,
        );
      }
      final entries = await p.getWeek(userId: h.userId, weekStart: week);
      await p.deleteEntry(id: entries.first.id, userId: h.userId);
      expect(await s.watchAll(h.userId).first, isNotEmpty);
    },
  );
  test(
    'when cooking an incompatible unit then stock is not silently consumed as grams',
    () async {
      final h = AppTestHarness();
      addTearDown(h.dispose);
      await h.container
          .read(pantryRepositoryProvider)
          .addItem(
            userId: h.userId,
            name: 'chicken breast',
            quantity: 3,
            unit: 'units',
            category: 'poultry',
          );
      final r = await recipe(h, 'Dinner', 200, 'g');
      final p = h.container.read(planRepositoryProvider);
      final e = await p.addEntry(
        userId: h.userId,
        recipeId: r,
        recipeTitle: 'Dinner',
        servings: 1,
      );
      try {
        await p.markCooked(entryId: e, userId: h.userId);
      } catch (_) {}
      expect(
        (await h.container.read(pantryRepositoryProvider).getAll(h.userId))
            .single
            .quantity,
        3,
      );
    },
  );
  gleanWidgetTest(
    'manual addition targets the week the user viewed, not today',
    (tester) async {
      final h = AppTestHarness();
      addTearDown(h.dispose);
      final r = await recipe(h, 'Future dinner', 200, 'g');
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Next week'));
      await tester.pumpAndSettle();
      h.router.go(AppRoutes.mealsDetailPath('$r'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Add to plan'));
      await tester.pumpAndSettle();
      final plan = h.container.read(planRepositoryProvider);
      expect(
        await tester.runAsync(
          () => plan.getWeek(userId: h.userId, weekStart: week),
        ),
        isEmpty,
      );
      expect(
        await tester.runAsync(
          () => plan.getWeek(
            userId: h.userId,
            weekStart: week.add(const Duration(days: 7)),
          ),
        ),
        hasLength(1),
      );
    },
  );
  gleanWidgetTest(
    'when manual planning fails to insert a gap then no meal remains half planned',
    (tester) async {
      final h = AppTestHarness();
      addTearDown(h.dispose);
      final r = await recipe(h, 'Dinner', 200, 'g');
      await h.db.customStatement(
        "CREATE TRIGGER fail_gaps BEFORE INSERT ON shopping_list_items BEGIN SELECT RAISE(ABORT, 'review gap failure'); END",
      );
      await h.pumpAt(tester, AppRoutes.mealsDetailPath('$r'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Add to plan'));
      await tester.pumpAndSettle();
      expect(
        tester.takeException(),
        isNull,
        reason: 'manual add failure must be surfaced, not uncaught',
      );
      expect(
        await h.container
            .read(planRepositoryProvider)
            .getWeek(userId: h.userId, weekStart: week),
        isEmpty,
      );
    },
  );
  gleanWidgetTest(
    'a title-only deleted-recipe meal still has complete deletion Undo',
    (tester) async {
      final h = AppTestHarness();
      addTearDown(h.dispose);
      final r = await recipe(h, 'Deleted recipe dinner', 200, 'g');
      final plan = h.container.read(planRepositoryProvider);
      final id = await plan.addEntry(
        userId: h.userId,
        recipeId: r,
        recipeTitle: 'Deleted recipe dinner',
        servings: 3,
        plannedDate: week,
      );
      await h.container
          .read(shoppingRepositoryProvider)
          .addGapsForRecipe(
            userId: h.userId,
            recipeId: r,
            servings: 3,
            sourceMealPlanEntryId: id,
          );
      await h.container
          .read(recipesRepositoryProvider)
          .deleteRecipe(id: r, userId: h.userId);
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      await tester.drag(
        find.text('Deleted recipe dinner'),
        const Offset(-600, 0),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();
      final restored = (await tester.runAsync(
        () => plan.getWeek(userId: h.userId, weekStart: week),
      ))!.single;
      expect(restored.id, id);
      expect(restored.recipeId, isNull);
      expect(restored.servings, 3);
      expect(
        (await tester.runAsync(
          () => h.container
              .read(shoppingRepositoryProvider)
              .watchAll(h.userId)
              .first,
        ))!.single.quantity,
        600,
      );
    },
  );

  gleanWidgetTest(
    'recipe deletion undo restores its original id and plan links',
    (tester) async {
      final h = AppTestHarness();
      addTearDown(h.dispose);
      final r = await recipe(h, 'Linked dinner', 200, 'g');
      final plan = h.container.read(planRepositoryProvider);
      await plan.addEntry(
        userId: h.userId,
        recipeId: r,
        recipeTitle: 'Linked dinner',
        servings: 1,
      );
      await h.pumpAt(tester, AppRoutes.mealsDetailPath('$r'));
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Remove from saved recipes'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();
      expect(
        await tester.runAsync(
          () => h.container
              .read(recipesRepositoryProvider)
              .getById(id: r, userId: h.userId),
        ),
        isNotNull,
      );
      expect(
        (await tester.runAsync(
          () => plan.getWeek(userId: h.userId, weekStart: week),
        ))!.single.recipeId,
        r,
      );
    },
  );

  gleanWidgetTest(
    'deleting and undoing a cooked meal preserves cooking and its reversible stock delta',
    (tester) async {
      final h = AppTestHarness();
      addTearDown(h.dispose);
      final pantry = h.container.read(pantryRepositoryProvider);
      await pantry.addItem(
        userId: h.userId,
        name: 'chicken breast',
        quantity: 100,
        unit: 'g',
        category: 'poultry',
      );
      final r = await recipe(h, 'Cooked dinner', 50, 'g');
      final plan = h.container.read(planRepositoryProvider);
      final e = await plan.addEntry(
        userId: h.userId,
        recipeId: r,
        recipeTitle: 'Cooked dinner',
        servings: 1,
      );
      await plan.markCooked(entryId: e, userId: h.userId);
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      await tester.drag(find.text('Cooked dinner'), const Offset(-600, 0));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();
      final restored = (await tester.runAsync(
        () => plan.getWeek(userId: h.userId, weekStart: week),
      ))!.single;
      expect(restored.id, e);
      expect(restored.isCooked, isTrue);
      expect(
        (await tester.runAsync(() => pantry.getAll(h.userId)))!.single.quantity,
        50,
      );
      await tester.runAsync(
        () => plan.undoCooked(entryId: e, userId: h.userId),
      );
      expect(
        (await tester.runAsync(() => pantry.getAll(h.userId)))!.single.quantity,
        100,
      );
    },
  );

  gleanWidgetTest(
    'user can undo deleting a meal without losing its shopping gaps',
    (tester) async {
      final h = AppTestHarness();
      addTearDown(h.dispose);
      final p = h.container.read(planRepositoryProvider);
      final s = h.container.read(shoppingRepositoryProvider);
      final r = await recipe(h, 'Dinner', 200, 'g');
      final e = await p.addEntry(
        userId: h.userId,
        recipeId: r,
        recipeTitle: 'Dinner',
        servings: 1,
      );
      await s.addGapsForRecipe(
        userId: h.userId,
        recipeId: r,
        servings: 1,
        sourceMealPlanEntryId: e,
      );
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      await tester.drag(find.text('Dinner'), const Offset(-600, 0));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();
      expect(
        await tester.runAsync(() => s.watchAll(h.userId).first),
        hasLength(1),
      );
    },
  );
  test(
    'when dinner capacity is reduced during Generate then persistence respects the new limit',
    () async {
      final client = MHttp();
      final h = AppTestHarness(httpClient: client);
      addTearDown(h.dispose);
      final requestSeen = Completer<void>();
      final pending = Completer<http.Response>();
      final ids = <String>[];
      for (final title in ['A', 'B', 'C']) {
        ids.add('rec_$title');
        await h.container
            .read(recipesRepositoryProvider)
            .save(
              userId: h.userId,
              externalId: 'rec_$title',
              title: title,
              ingredients: const [],
            );
      }
      when(
        () => client.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer((_) {
        requestSeen.complete();
        return pending.future;
      });
      final op = h.container
          .read(generateWeekControllerProvider.notifier)
          .generate(weekStart: week, slots: 3, servings: 1);
      await requestSeen.future;
      await h.container
          .read(userConfigRepositoryProvider)
          .save(
            UserConfigView(
              id: h.userId,
              purchaseTolerance: 0.5,
              preferredServings: 1,
              mealsPerWeek: 1,
              dietaryFlags: const [],
              maxActiveTimeMins: null,
            ),
          );
      pending.complete(
        http.Response(
          jsonEncode({
            'suggestions': [
              for (final id in ids)
                {
                  'recipe_id': null,
                  'external_id': id,
                  'title': 'Dinner',
                  'reason': 'fit',
                },
            ],
          }),
          200,
        ),
      );
      await op;
      expect(
        await h.container
            .read(planRepositoryProvider)
            .getWeek(userId: h.userId, weekStart: week),
        hasLength(1),
      );
    },
  );
  gleanWidgetTest(
    'when receipt checkout deletion fails then pantry commit is rolled back',
    (tester) async {
      final h = AppTestHarness();
      addTearDown(h.dispose);
      final s = h.container.read(shoppingRepositoryProvider);
      final id = await s.addManualItem(
        userId: h.userId,
        name: 'chicken breast',
        quantity: 100,
        unit: 'g',
      );
      await s.toggleItem(id: id, userId: h.userId, checked: true);
      await h.db.customStatement(
        "CREATE TRIGGER fail_checkout BEFORE DELETE ON shopping_list_items BEGIN SELECT RAISE(ABORT, 'review checkout failure'); END",
      );
      unawaited(
        h.router.pushNamed(
          AppRoutes.intakeReview.name,
          extra: const ReviewArgs(
            destination: ReviewDestination.pantry,
            returnToShop: true,
            items: [
              ReviewItemDraft(
                reviewId: 'a',
                name: 'chicken breast',
                quantity: 100,
                unit: 'g',
                confidence: 1,
                category: 'poultry',
              ),
            ],
          ),
        ),
      );
      await tester.pumpWidget(h.app());
      await tester.pumpAndSettle();
      await tester.tap(find.text('Add 1 item'));
      await pumpUntil(
        tester,
        () => find
            .text('Could not save. Please try again.')
            .evaluate()
            .isNotEmpty,
        description: 'checkout rollback feedback',
      );
      expect(
        await tester.runAsync(
          () => h.container.read(pantryRepositoryProvider).getAll(h.userId),
        ),
        isEmpty,
      );
      expect(
        (await tester.runAsync(
          () => s.watchAll(h.userId).first,
        ))!.single.isChecked,
        isTrue,
      );
      await tester.runAsync(
        () => h.db.customStatement('DROP TRIGGER fail_checkout'),
      );
      // Settle the entering snackbar, then dismiss it with the user's gesture.
      await tester.pumpAndSettle();
      await tester.drag(
        find.text('Could not save. Please try again.'),
        const Offset(0, 200),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Add 1 item'));
      await pumpUntil(
        tester,
        () => find.text('Added 1 item').evaluate().isNotEmpty,
        description: 'checkout retry completion',
      );
      expect(
        (await tester.runAsync(
          () => h.container.read(pantryRepositoryProvider).getAll(h.userId),
        ))!.single.quantity,
        100,
      );
      expect(await tester.runAsync(() => s.watchAll(h.userId).first), isEmpty);
    },
  );
}
