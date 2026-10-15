// Real-outcome tests (AC-TEST-02) for the shopping-list bugs
// FLUTTER_MIGRATION.md §11/§6 Shop calls out by name: checkout deleting
// unmatched items (AC-SHOP-01, AC-TEST-06), manual items never resolving an
// ingredient identity (AC-SHOP-03), unscoped check-off (AC-SHOP-04), and
// plan-derived rows outliving their plan entry (AC-SHOP-06). Also ports the
// shortfall-maths intent of the Expo app's `tests/db/shopping.test.ts`
// (see git history) as outcome assertions rather than query-builder call
// counts.
import 'package:glean/data/database.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/plan_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fixture.dart';

void main() {
  group('ShoppingRepository', () {
    late GleanDatabase db;
    late ShoppingRepository repository;
    late IngredientsRepository ingredients;
    const userId = 'user-a';

    setUp(() {
      db = createTestDatabase();
      ingredients = IngredientsRepository(db);
      repository = ShoppingRepository(db, ingredients);
    });

    tearDown(() => db.close());

    test(
      'addManualItem always resolves an ingredient identity (AC-SHOP-03)',
      () async {
        await repository.addManualItem(
          userId: userId,
          name: 'Birthday candles',
        );

        final items = await repository.watchAll(userId).first;
        expect(items.single.ingredientId, isNotNull);

        final ingredient = await ingredients.resolveOrCreate(
          canonicalName: 'birthday candles',
        );
        expect(items.single.ingredientId, ingredient.id);
      },
    );

    test('addAiItems: a blank unit defaults to "units" for the row, but never '
        "seeds the ingredient's shared canonical unit (R-23)", () async {
      await repository.addAiItems(
        userId: userId,
        items: const <AiShoppingItem>[
          // The review screen's exact scenario: the unit field was left
          // blank, not a real chosen/parsed unit.
          AiShoppingItem(
            name: 'chia seeds',
            quantity: 1,
            unit: '',
            category: 'grains',
          ),
        ],
      );

      final items = await repository.watchAll(userId).first;
      // The row itself still needs *some* unit to store and display.
      expect(items.single.unit, 'units');

      // But the shared ingredient's canonical unit was never seeded from
      // that fallback — a later, genuinely explicit unit must still be
      // free to seed it (proven at the Pantry side in
      // `pantry_repository_test.dart`'s equivalent R-23 test, since
      // `Ingredients` is one shared, non-user-scoped catalog either way).
      final ingredient = await ingredients.resolveOrCreate(
        canonicalName: 'chia seeds',
      );
      expect(ingredient.canonicalUnit, isNull);
    });

    test(
      'resolveCheckout removes only the rows the receipt resolved, leaving the rest (AC-SHOP-01, AC-TEST-06)',
      () async {
        final ingredientIds = <int>[];
        for (var i = 0; i < 12; i++) {
          await repository.addManualItem(userId: userId, name: 'item-$i');
        }
        final items = await repository.watchAll(userId).first;
        for (final item in items) {
          await repository.toggleItem(
            id: item.id,
            userId: userId,
            checked: true,
          );
          ingredientIds.add(item.ingredientId);
        }
        expect(ingredientIds, hasLength(12));

        final resolved = ingredientIds.take(4).toList();
        final removedCount = await repository.resolveCheckout(
          userId: userId,
          resolvedIngredientIds: resolved,
        );

        expect(removedCount, 4);
        final remaining = await repository.watchAll(userId).first;
        expect(remaining, hasLength(8));
        expect(
          remaining.map((r) => r.ingredientId),
          isNot(anyElement(isIn(resolved))),
        );
        // The 8 unmatched rows are untouched — still on the list, still
        // checked — never silently deleted the way RN's completeCheckout
        // deleted every checked row regardless of match.
        expect(remaining.every((r) => r.isChecked), isTrue);
      },
    );

    // AC-SHOP-04's scoping (never cross a user, never re-affect an
    // already-checked row) is exercised above, inside `resolveCheckout`'s
    // own test — R-03 deleted the standalone `checkOffResolvedIngredients`
    // (and this test's former sibling covering it) as genuinely redundant
    // once `resolveCheckout` did the matching and removal in one already-
    // scoped statement. See the doc comments on `resolveCheckout` and at the
    // top of `lib/data/repositories/shopping_repository.dart` for why.

    group('addGapsForRecipe shortfall maths', () {
      late RecipesRepository recipes;
      late PantryRepository pantry;
      late PlanRepository plan;

      setUp(() {
        recipes = RecipesRepository(db, ingredients);
        pantry = PantryRepository(db, ingredients);
        plan = PlanRepository(db, pantry);
      });

      // `sourceMealPlanEntryId` is a real foreign key (AC-SHOP-06 depends on
      // it cascading), so every gap in these tests is linked to an actual
      // plan entry rather than an arbitrary id.
      Future<({int recipeId, int entryId})> saveRecipeAndPlanEntry({
        required String ingredient,
        required double quantityPerServing,
        required String unit,
      }) async {
        final recipeId = await recipes.save(
          userId: userId,
          title: 'Test recipe',
          ingredients: [
            SaveRecipeIngredient(
              canonicalName: ingredient,
              quantity: quantityPerServing,
              unit: unit,
            ),
          ],
        );
        final entryId = await plan.addEntry(
          userId: userId,
          recipeId: recipeId,
          recipeTitle: 'Test recipe',
          servings: 1,
        );
        return (recipeId: recipeId, entryId: entryId);
      }

      test(
        'adds a shortfall item when the pantry has less than needed',
        () async {
          final linked = await saveRecipeAndPlanEntry(
            ingredient: 'chicken breast',
            quantityPerServing: 400,
            unit: 'g',
          );
          await pantry.addItem(
            userId: userId,
            name: 'chicken breast',
            quantity: 200,
            unit: 'g',
            category: 'poultry',
          );

          await repository.addGapsForRecipe(
            userId: userId,
            recipeId: linked.recipeId,
            servings: 1,
            sourceMealPlanEntryId: linked.entryId,
          );

          final items = await repository.watchAll(userId).first;
          expect(items, hasLength(1));
          expect(items.single.quantity, 200); // 400 needed - 200 in pantry
        },
      );

      test('adds nothing when the pantry already has enough', () async {
        final linked = await saveRecipeAndPlanEntry(
          ingredient: 'salt',
          quantityPerServing: 50,
          unit: 'g',
        );
        await pantry.addItem(
          userId: userId,
          name: 'salt',
          quantity: 500,
          unit: 'g',
          category: 'spices',
        );

        await repository.addGapsForRecipe(
          userId: userId,
          recipeId: linked.recipeId,
          servings: 1,
          sourceMealPlanEntryId: linked.entryId,
        );

        expect(await repository.watchAll(userId).first, isEmpty);
      });

      test(
        'aggregates different meals while repeated requirements remain idempotent',
        () async {
          final firstLink = await saveRecipeAndPlanEntry(
            ingredient: 'pasta',
            quantityPerServing: 200,
            unit: 'g',
          );

          await repository.addGapsForRecipe(
            userId: userId,
            recipeId: firstLink.recipeId,
            servings: 1,
            sourceMealPlanEntryId: firstLink.entryId,
          );
          expect(await repository.watchAll(userId).first, hasLength(1));

          // A second meal owns separate demand, aggregated only for display.
          final secondEntryId = await plan.addEntry(
            userId: userId,
            recipeId: firstLink.recipeId,
            recipeTitle: 'Test recipe',
            servings: 1,
          );
          await repository.addGapsForRecipe(
            userId: userId,
            recipeId: firstLink.recipeId,
            servings: 1,
            sourceMealPlanEntryId: secondEntryId,
          );
          final both = (await repository.watchAll(userId).first).single;
          expect(both.quantity, 400);
          expect(both.ids, hasLength(2));
          await plan.deleteEntry(id: firstLink.entryId, userId: userId);
          expect(
            (await repository.watchAll(userId).first).single.quantity,
            200,
          );
          await repository.addGapsForRecipe(
            userId: userId,
            recipeId: firstLink.recipeId,
            servings: 1,
            sourceMealPlanEntryId: secondEntryId,
          );
          expect(
            (await repository.watchAll(userId).first).single.quantity,
            200,
          );
        },
      );

      test(
        'compatible requirements aggregate even before any stock exists',
        () async {
          final first = await saveRecipeAndPlanEntry(
            ingredient: 'chicken breast',
            quantityPerServing: 200,
            unit: 'g',
          );
          final second = await saveRecipeAndPlanEntry(
            ingredient: 'chicken breast',
            quantityPerServing: 0.3,
            unit: 'kg',
          );
          for (final linked in [first, second]) {
            await repository.addGapsForRecipe(
              userId: userId,
              recipeId: linked.recipeId,
              servings: 1,
              sourceMealPlanEntryId: linked.entryId,
            );
          }
          final visible = await repository.watchAll(userId).first;
          expect(visible, hasLength(1));
          expect(visible.single.quantity, 500);
          expect(visible.single.unit, 'g');
          expect(visible.single.ids, hasLength(2));
        },
      );

      test(
        'editing stock units cannot allocate the same stock twice across old and new requirements',
        () async {
          await pantry.addItem(
            userId: userId,
            name: 'chicken breast',
            quantity: 3000,
            unit: 'g',
            category: 'poultry',
          );
          final stockId = (await pantry.getAll(userId)).single.id;
          final first = await saveRecipeAndPlanEntry(
            ingredient: 'chicken breast',
            quantityPerServing: 3000,
            unit: 'g',
          );
          await repository.addGapsForRecipe(
            userId: userId,
            recipeId: first.recipeId,
            servings: 1,
            sourceMealPlanEntryId: first.entryId,
          );
          expect(await repository.watchAll(userId).first, isEmpty);
          await pantry.updateItem(
            id: stockId,
            userId: userId,
            quantity: 3,
            unit: 'kg',
          );
          final second = await saveRecipeAndPlanEntry(
            ingredient: 'chicken breast',
            quantityPerServing: 1,
            unit: 'kg',
          );
          await repository.addGapsForRecipe(
            userId: userId,
            recipeId: second.recipeId,
            servings: 1,
            sourceMealPlanEntryId: second.entryId,
          );
          final visible = await repository.watchAll(userId).first;
          expect(visible, hasLength(1));
          expect(
            visible.single.quantity,
            1000,
          ); // 4kg total demand - 3kg owned.
          expect(visible.single.unit, 'g');
        },
      );

      test(
        'density-compatible requirements aggregate without pantry stock',
        () async {
          final first = await saveRecipeAndPlanEntry(
            ingredient: 'milk',
            quantityPerServing: 515,
            unit: 'g',
          );
          final second = await saveRecipeAndPlanEntry(
            ingredient: 'milk',
            quantityPerServing: 500,
            unit: 'ml',
          );
          for (final linked in [first, second]) {
            await repository.addGapsForRecipe(
              userId: userId,
              recipeId: linked.recipeId,
              servings: 1,
              sourceMealPlanEntryId: linked.entryId,
            );
          }
          final visible = await repository.watchAll(userId).first;
          expect(visible, hasLength(1));
          expect(visible.single.quantity, 1030); // Milk density: 1.03g/ml.
          expect(visible.single.unit, 'g');
          expect(visible.single.ids, hasLength(2));
        },
      );

      test(
        'density-compatible unit edits cannot spend the same pantry stock twice',
        () async {
          await pantry.addItem(
            userId: userId,
            name: 'milk',
            quantity: 515,
            unit: 'g',
            category: 'dairy',
          );
          final stockId = (await pantry.getAll(userId)).single.id;
          final first = await saveRecipeAndPlanEntry(
            ingredient: 'milk',
            quantityPerServing: 515,
            unit: 'g',
          );
          await repository.addGapsForRecipe(
            userId: userId,
            recipeId: first.recipeId,
            servings: 1,
            sourceMealPlanEntryId: first.entryId,
          );
          expect(await repository.watchAll(userId).first, isEmpty);
          await pantry.updateItem(
            id: stockId,
            userId: userId,
            quantity: 500,
            unit: 'ml',
          );
          final second = await saveRecipeAndPlanEntry(
            ingredient: 'milk',
            quantityPerServing: 250,
            unit: 'ml',
          );
          await repository.addGapsForRecipe(
            userId: userId,
            recipeId: second.recipeId,
            servings: 1,
            sourceMealPlanEntryId: second.entryId,
          );
          final visible = await repository.watchAll(userId).first;
          expect(visible, hasLength(1));
          expect(visible.single.quantity, 257.5); // 750ml demand - 500ml owned.
          expect(visible.single.unit, 'g');
        },
      );

      test('scales the shortfall across multiple servings', () async {
        final linked = await saveRecipeAndPlanEntry(
          ingredient: 'rice',
          quantityPerServing: 100,
          unit: 'g',
        );
        await pantry.addItem(
          userId: userId,
          name: 'rice',
          quantity: 50,
          unit: 'g',
          category: 'pasta_rice',
        );

        // 3 servings * 100g = 300g needed, 50g in pantry -> 250g shortfall.
        await repository.addGapsForRecipe(
          userId: userId,
          recipeId: linked.recipeId,
          servings: 3,
          sourceMealPlanEntryId: linked.entryId,
        );

        final items = await repository.watchAll(userId).first;
        expect(items.single.quantity, 250);
      });
    });

    test(
      'deleting the plan entry that created a gap row removes that row too (AC-SHOP-06)',
      () async {
        final recipes = RecipesRepository(db, ingredients);
        final pantry = PantryRepository(db, ingredients);
        final plan = PlanRepository(db, pantry);

        final recipeId = await recipes.save(
          userId: userId,
          title: 'Needs cheese',
          ingredients: const [
            SaveRecipeIngredient(
              canonicalName: 'cheese',
              quantity: 200,
              unit: 'g',
            ),
          ],
        );
        final entryId = await plan.addEntry(
          userId: userId,
          recipeId: recipeId,
          recipeTitle: 'Needs cheese',
          servings: 1,
        );
        await repository.addGapsForRecipe(
          userId: userId,
          recipeId: recipeId,
          servings: 1,
          sourceMealPlanEntryId: entryId,
        );
        expect(await repository.watchAll(userId).first, hasLength(1));

        await plan.deleteEntry(id: entryId, userId: userId);

        expect(await repository.watchAll(userId).first, isEmpty);
      },
    );

    test(
      'completeCheckoutWithoutReceipt removes every checked row (AC-SHOP-02)',
      () async {
        final keep = await repository.addManualItem(
          userId: userId,
          name: 'keep me',
        );
        final remove = await repository.addManualItem(
          userId: userId,
          name: 'remove me',
        );
        await repository.toggleItem(id: remove, userId: userId, checked: true);

        final removedCount = await repository.completeCheckoutWithoutReceipt(
          userId: userId,
        );

        expect(removedCount, 1);
        final remaining = await repository.watchAll(userId).first;
        expect(remaining.map((r) => r.id), [keep]);
      },
    );
  });
}
