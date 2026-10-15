import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/providers/clock_provider.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/router/app_routes.dart';
import '../../support/harness.dart';

void main() {
  test(
    'rollover fills only remaining capacity and leaves excess in original weeks',
    () async {
      final h = AppTestHarness();
      addTearDown(h.dispose);
      final week = startOfWeek(DateTime(2026, 10, 7));
      await h.container
          .read(userConfigRepositoryProvider)
          .save(
            UserConfigView(
              id: h.userId,
              purchaseTolerance: 0.5,
              preferredServings: 1,
              mealsPerWeek: 2,
              dietaryFlags: const [],
              maxActiveTimeMins: null,
            ),
          );
      final recipes = h.container.read(recipesRepositoryProvider);
      final plan = h.container.read(planRepositoryProvider);
      final r = await recipes.save(
        userId: h.userId,
        title: 'Dinner',
        ingredients: const [],
      );
      await plan.addEntry(
        userId: h.userId,
        recipeId: r,
        recipeTitle: 'Current',
        servings: 1,
        plannedDate: week,
      );
      for (var i = 0; i < 3; i++) {
        await plan.addEntry(
          userId: h.userId,
          recipeId: r,
          recipeTitle: 'Old $i',
          servings: 1,
          plannedDate: week.subtract(const Duration(days: 7)),
        );
      }
      await plan.rolloverUncookedMeals(userId: h.userId, referenceDate: week);
      expect(
        await plan.getWeek(userId: h.userId, weekStart: week),
        hasLength(2),
      );
      expect(
        await plan.getWeek(
          userId: h.userId,
          weekStart: week.subtract(const Duration(days: 7)),
        ),
        hasLength(2),
      );
      await plan.rolloverUncookedMeals(userId: h.userId, referenceDate: week);
      expect(
        await plan.getWeek(userId: h.userId, weekStart: week),
        hasLength(2),
      );
    },
  );

  gleanWidgetTest(
    'Monday rolls uncooked meals once while Plan remains mounted',
    (tester) async {
      var clock = DateTime(2026, 10, 11, 23, 59, 59);
      final h = AppTestHarness(
        overrides: [clockProvider.overrideWithValue(() => clock)],
      );
      addTearDown(h.dispose);
      final oldWeek = startOfWeek(clock);
      final nextWeek = DateTime(2026, 10, 12);
      final r = await h.container
          .read(recipesRepositoryProvider)
          .save(userId: h.userId, title: 'Dinner', ingredients: const []);
      final plan = h.container.read(planRepositoryProvider);
      final ids = <int>[];
      for (var i = 0; i < 2; i++) {
        ids.add(
          await plan.addEntry(
            userId: h.userId,
            recipeId: r,
            recipeTitle: 'Dinner $i',
            servings: 1,
            plannedDate: oldWeek,
          ),
        );
      }
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      clock = nextWeek;
      await tester.pump(const Duration(seconds: 2));
      await tester.pumpAndSettle();
      expect(
        await tester.runAsync(
          () => plan.getWeek(userId: h.userId, weekStart: oldWeek),
        ),
        isEmpty,
      );
      expect(
        (await tester.runAsync(
          () => plan.getWeek(userId: h.userId, weekStart: nextWeek),
        ))!.map((e) => e.id),
        unorderedEquals(ids),
      );
      await tester.pump(const Duration(seconds: 3));
      await tester.pumpAndSettle();
      expect(
        await tester.runAsync(
          () => plan.getWeek(userId: h.userId, weekStart: nextWeek),
        ),
        hasLength(2),
      );
    },
  );
}
