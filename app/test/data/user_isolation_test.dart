// New coverage 2 (FLUTTER_MIGRATION.md §10): user-scoped data isolation.
// Today only `user_config` is keyed by user — `pantry_items`, `recipes`,
// `meal_plan_entries` and `shopping_list_items` have none, so signing in as
// a different account on the same device inherited the previous user's
// groceries (AC-DATA-02/03, AC-TEST-07).
import 'package:glean/data/database.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/plan_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fixture.dart';

void main() {
  group('user-scoped isolation (AC-TEST-07)', () {
    late GleanDatabase db;
    late PantryRepository pantry;
    late RecipesRepository recipes;
    late PlanRepository plan;
    late ShoppingRepository shopping;
    const userA = 'user-a';
    const userB = 'user-b';

    setUp(() {
      db = createTestDatabase();
      final ingredients = IngredientsRepository(db);
      pantry = PantryRepository(db, ingredients);
      recipes = RecipesRepository(db, ingredients);
      plan = PlanRepository(db, pantry);
      shopping = ShoppingRepository(db, ingredients);
    });

    tearDown(() => db.close());

    test("user A's pantry is invisible to user B on the same device", () async {
      await pantry.addItem(
        userId: userA,
        name: 'milk',
        quantity: 1,
        unit: 'l',
        category: 'dairy',
      );

      expect(await pantry.watchAll(userA).first, hasLength(1));
      expect(await pantry.watchAll(userB).first, isEmpty);
    });

    test("user A's saved recipes are invisible to user B", () async {
      await recipes.save(
        userId: userA,
        title: "A's recipe",
        ingredients: const [],
      );

      expect(await recipes.watchSaved(userA).first, hasLength(1));
      expect(await recipes.watchSaved(userB).first, isEmpty);
    });

    test("user A's plan entries are invisible to user B", () async {
      final recipeId = await recipes.save(
        userId: userA,
        title: "A's recipe",
        ingredients: const [],
      );
      await plan.addEntry(
        userId: userA,
        recipeId: recipeId,
        recipeTitle: "A's recipe",
        servings: 2,
      );

      final week = DateTime.now();
      expect(
        await plan.watchWeek(userId: userA, weekStart: week).first,
        isNotEmpty,
      );
      expect(
        await plan.watchWeek(userId: userB, weekStart: week).first,
        isEmpty,
      );
    });

    test("user A's shopping list is invisible to user B", () async {
      await shopping.addManualItem(userId: userA, name: 'candles');

      expect(await shopping.watchAll(userA).first, hasLength(1));
      expect(await shopping.watchAll(userB).first, isEmpty);
    });

    test(
      'same ingredient name resolves to the same shared ingredient row for both users',
      () async {
        // The ingredient catalog itself is intentionally shared (it is not
        // user data) — only pantry/recipe/plan/shopping rows are scoped.
        await pantry.addItem(
          userId: userA,
          name: 'garlic',
          quantity: 3,
          unit: 'unit',
          category: 'alliums',
        );
        await pantry.addItem(
          userId: userB,
          name: 'garlic',
          quantity: 5,
          unit: 'unit',
          category: 'alliums',
        );

        final aItems = await pantry.watchAll(userA).first;
        final bItems = await pantry.watchAll(userB).first;
        expect(aItems.single.ingredientId, bItems.single.ingredientId);
        expect(aItems.single.quantity, 3);
        expect(bItems.single.quantity, 5);
      },
    );

    test('writes scoped by id and userId cannot cross users', () async {
      await shopping.addManualItem(userId: userA, name: 'flour');
      final item = (await shopping.watchAll(userA).first).single;

      // user B attempting to toggle/delete user A's row by id has no effect.
      await shopping.toggleItem(id: item.id, userId: userB, checked: true);
      final stillA = (await shopping.watchAll(userA).first).single;
      expect(stillA.isChecked, isFalse);

      await shopping.deleteItem(id: item.id, userId: userB);
      expect(await shopping.watchAll(userA).first, hasLength(1));
    });
  });
}
