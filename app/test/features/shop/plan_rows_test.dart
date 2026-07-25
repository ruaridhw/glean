// AC-SHOP-05/06: a plan-derived shopping row carries a visible "From plan"
// tag (this module's contribution to "announce" — see
// `presentation.dart`'s `isPlanDerived` doc for why the insertion-time
// snackbar itself is the Plan feature's job, not this one's), and deleting
// the plan entry that created a row removes the row live, with no
// `ref.invalidate` anywhere — just the schema's cascade plus the drift
// stream re-emitting.
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/plan_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:glean/router/app_routes.dart';

import '../../support/harness.dart';

void main() {
  group('Plan-derived shopping rows', () {
    late AppTestHarness harness;
    late ShoppingRepository shopping;
    late RecipesRepository recipes;
    late PlanRepository plan;

    setUp(() {
      harness = AppTestHarness();
      final ingredients = IngredientsRepository(harness.db);
      shopping = ShoppingRepository(harness.db, ingredients);
      recipes = RecipesRepository(harness.db, ingredients);
      plan = PlanRepository(
        harness.db,
        PantryRepository(harness.db, ingredients),
      );
    });

    tearDown(() => harness.dispose());

    testWidgets(
      'a plan-derived row is tagged "From plan" and disappears when its '
      'plan entry is deleted (AC-SHOP-05/06)',
      (WidgetTester tester) async {
        final int recipeId = await recipes.save(
          userId: 'test-user',
          title: 'Tomato Soup',
          ingredients: const <SaveRecipeIngredient>[
            SaveRecipeIngredient(
              canonicalName: 'Tomatoes',
              quantity: 4,
              unit: 'pcs',
            ),
          ],
        );
        final int entryId = await plan.addEntry(
          userId: 'test-user',
          recipeId: recipeId,
          recipeTitle: 'Tomato Soup',
          servings: 2,
        );
        // Nothing in the pantry, so the whole recipe quantity is a shortfall
        // — this is the same call the Plan feature makes after "Add to
        // plan"/generate (outside this module's files).
        await shopping.addGapsForRecipe(
          userId: 'test-user',
          recipeId: recipeId,
          servings: 2,
          sourceMealPlanEntryId: entryId,
        );

        await harness.pumpAt(tester, AppRoutes.shop.path);
        await tester.pumpAndSettle();

        // `IngredientsRepository.resolveOrCreate` lower-cases the canonical
        // name it resolves, and `addGapsForRecipe` uses that canonical name
        // verbatim as the row's display name (unlike `addManualItem`, which
        // keeps the user's own typed casing) — so this row reads "tomatoes",
        // not "Tomatoes". It's rendered as part of a combined
        // "name · quantity unit" label, hence `textContaining` rather than
        // an exact match.
        expect(find.textContaining('tomatoes'), findsOneWidget);
        expect(find.text('From plan'), findsOneWidget);

        await plan.deleteEntry(id: entryId, userId: 'test-user');
        await tester.pumpAndSettle();

        // No `ref.invalidate` anywhere in this module (AC-DATA-05) — the
        // schema's `onDelete: cascade` removed the row, and the same
        // `shoppingListProvider` stream this screen already watches just
        // re-emitted without it.
        expect(find.textContaining('tomatoes'), findsNothing);
        expect(
          await tester.runAsync(() => shopping.watchAll('test-user').first),
          isEmpty,
        );
      },
    );

    testWidgets('a manually-added row carries no plan tag', (
      WidgetTester tester,
    ) async {
      await shopping.addManualItem(userId: 'test-user', name: 'Bananas');

      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();

      expect(find.text('Bananas'), findsOneWidget);
      expect(find.text('From plan'), findsNothing);
    });
  });
}
