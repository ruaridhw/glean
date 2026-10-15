// a plan-derived shopping row carries a visible "From plan"
// tag (this module's contribution to "announce" — see
// `presentation.dart`'s `isPlanDerived` doc for why the insertion-time
// snackbar itself is the Plan feature's job, not this one's), and deleting
// the plan entry that created a row removes the row live, with no
// `ref.invalidate` anywhere — just the schema's cascade plus the drift
// stream re-emitting.
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/plan_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:glean/router/app_routes.dart';

import '../../support/harness.dart';

void main() {
  group('Plan-derived shopping rows', () {
    late AppTestHarness harness;

    // Read lazily: touching `harness.container` in `setUp` would start drift
    // work outside the test's fake-async zone.
    ShoppingRepository shopping() =>
        harness.container.read(shoppingRepositoryProvider);
    RecipesRepository recipes() =>
        harness.container.read(recipesRepositoryProvider);
    PlanRepository plan() => harness.container.read(planRepositoryProvider);

    setUp(() => harness = AppTestHarness());

    tearDown(() => harness.dispose());

    testWidgets(
      'a plan-derived row is tagged "From plan" and disappears when its '
      'plan entry is deleted',
      (WidgetTester tester) async {
        final int recipeId = await recipes().save(
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
        final int entryId = await plan().addEntry(
          userId: 'test-user',
          recipeId: recipeId,
          recipeTitle: 'Tomato Soup',
          servings: 2,
        );
        // Nothing in the pantry, so the whole recipe quantity is a shortfall
        // — this is the same call the Plan feature makes after "Add to
        // plan"/generate (outside this module's files).
        await shopping().addGapsForRecipe(
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

        await plan().deleteEntry(id: entryId, userId: 'test-user');
        await tester.pumpAndSettle();

        // No `ref.invalidate` anywhere in this module — the
        // schema's `onDelete: cascade` removed the row, and the same
        // `shoppingListProvider` stream this screen already watches just
        // re-emitted without it.
        expect(find.textContaining('tomatoes'), findsNothing);
        expect(
          await tester.runAsync(() => shopping().watchAll('test-user').first),
          isEmpty,
        );
      },
    );

    testWidgets('a manually-added row carries no plan tag', (
      WidgetTester tester,
    ) async {
      await shopping().addManualItem(userId: 'test-user', name: 'Bananas');

      await harness.pumpAt(tester, AppRoutes.shop.path);
      await tester.pumpAndSettle();

      expect(find.text('Bananas'), findsOneWidget);
      expect(find.text('From plan'), findsNothing);
    });

    group('"for <recipe>" subtitle', () {
      Future<int> planRecipe(String title, {String needing = 'spinach'}) async {
        final int recipeId = await recipes().save(
          userId: 'test-user',
          title: title,
          ingredients: <SaveRecipeIngredient>[
            SaveRecipeIngredient(
              canonicalName: needing,
              quantity: 100,
              unit: 'g',
            ),
          ],
        );
        final int entryId = await plan().addEntry(
          userId: 'test-user',
          recipeId: recipeId,
          recipeTitle: title,
          servings: 1,
        );
        await shopping().addGapsForRecipe(
          userId: 'test-user',
          recipeId: recipeId,
          servings: 1,
          sourceMealPlanEntryId: entryId,
        );
        return recipeId;
      }

      testWidgets('a to-buy item from one planned recipe says who it is for', (
        WidgetTester tester,
      ) async {
        await planRecipe('Spinach & feta pasta');

        await harness.pumpAt(tester, AppRoutes.shop.path);
        await tester.pumpAndSettle();

        expect(find.text('for Spinach & feta pasta'), findsOneWidget);
      });

      testWidgets('a manually-added item shows no subtitle', (
        WidgetTester tester,
      ) async {
        await shopping().addManualItem(userId: 'test-user', name: 'Bananas');

        await harness.pumpAt(tester, AppRoutes.shop.path);
        await tester.pumpAndSettle();

        expect(find.textContaining('for '), findsNothing);
      });

      testWidgets('an item merged from two planned recipes names both', (
        WidgetTester tester,
      ) async {
        await planRecipe('Spinach & feta pasta');
        await planRecipe('Saag paneer');

        await harness.pumpAt(tester, AppRoutes.shop.path);
        await tester.pumpAndSettle();

        expect(
          find.text('for Spinach & feta pasta and Saag paneer'),
          findsOneWidget,
        );
      });

      testWidgets('an item merged from many planned recipes truncates with a '
          'count', (WidgetTester tester) async {
        await planRecipe('Pasta');
        await planRecipe('Saag paneer');
        await planRecipe('Omelette');
        await planRecipe('Dal');

        await harness.pumpAt(tester, AppRoutes.shop.path);
        await tester.pumpAndSettle();

        expect(find.text('for Pasta, Saag paneer +2 more'), findsOneWidget);
      });

      testWidgets('the subtitle still shows after the recipe is deleted from '
          'the library', (WidgetTester tester) async {
        final int recipeId = await planRecipe('Spinach & feta pasta');
        await recipes().deleteRecipe(id: recipeId, userId: 'test-user');

        await harness.pumpAt(tester, AppRoutes.shop.path);
        await tester.pumpAndSettle();

        expect(find.text('for Spinach & feta pasta'), findsOneWidget);
      });

      testWidgets('an in-cart item shows no subtitle', (
        WidgetTester tester,
      ) async {
        await planRecipe('Spinach & feta pasta');
        final item = (await tester.runAsync(
          () => shopping().watchAll('test-user').first,
        ))!.single;
        await tester.runAsync(
          () => shopping().toggleRows(
            ids: item.ids,
            userId: 'test-user',
            checked: true,
          ),
        );

        await harness.pumpAt(tester, AppRoutes.shop.path);
        await tester.pumpAndSettle();

        expect(find.textContaining('spinach'), findsOneWidget);
        expect(find.textContaining('for '), findsNothing);
      });
    });
  });
}
