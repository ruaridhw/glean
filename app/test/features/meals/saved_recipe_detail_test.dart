// Widget coverage for the saved-recipe detail screen: `not_suitable_for`
// and `source_url` render when present and degrade cleanly when absent
// (AC-MEAL-04/05), the bookmark is a real unsave toggle (AC-MEAL-02), and a
// missing recipe recovers instead of hanging (AC-MEAL-12).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/route_error_screen.dart';

import '../../support/harness.dart';

void main() {
  group('SavedRecipeDetail', () {
    late AppTestHarness harness;
    late RecipesRepository recipes;

    setUp(() {
      harness = AppTestHarness();
      recipes = RecipesRepository(
        harness.db,
        IngredientsRepository(harness.db),
      );
    });

    tearDown(() => harness.dispose());

    testWidgets('renders not_suitable_for and source_url when present', (
      WidgetTester tester,
    ) async {
      final int id = await recipes.save(
        userId: 'test-user',
        externalId: 'ext-1',
        title: 'Peanut Noodles',
        sourceUrl: 'https://cooking.example.com/peanut-noodles',
        notSuitableFor: const <String>['nuts', 'soy'],
        ingredients: const <SaveRecipeIngredient>[],
      );

      await harness.pumpAt(tester, AppRoutes.mealsDetailPath('$id'));
      await tester.pumpAndSettle();

      expect(
        find.textContaining('Not suitable for: nuts, soy'),
        findsOneWidget,
      );
      expect(
        find.textContaining('Imported from cooking.example.com'),
        findsOneWidget,
      );
    });

    testWidgets('degrades cleanly when both are absent', (
      WidgetTester tester,
    ) async {
      final int id = await recipes.save(
        userId: 'test-user',
        externalId: 'ext-2',
        title: 'Plain Rice',
        ingredients: const <SaveRecipeIngredient>[],
      );

      await harness.pumpAt(tester, AppRoutes.mealsDetailPath('$id'));
      await tester.pumpAndSettle();
      await tester.pump();

      expect(find.textContaining('Not suitable for'), findsNothing);
      expect(find.textContaining('Imported from'), findsNothing);
    });

    testWidgets(
      'the bookmark unsaves with undo and leaves this recipe\'s own detail '
      'screen (AC-MEAL-02/12 — never left stranded on a deleted recipe)',
      (WidgetTester tester) async {
        final int id = await recipes.save(
          userId: 'test-user',
          externalId: 'ext-3',
          title: 'Lentil Soup',
          ingredients: const <SaveRecipeIngredient>[],
        );

        await harness.pumpAt(tester, AppRoutes.mealsDetailPath('$id'));
        await tester.pumpAndSettle();
        expect(
          find.descendant(
            of: find.byType(AppBar),
            matching: find.text('Lentil Soup'),
          ),
          findsOneWidget,
        );

        await tester.tap(find.byIcon(Icons.bookmark_rounded));
        await tester.pumpAndSettle();

        expect(find.text('Lentil Soup removed'), findsOneWidget);
        // A raw repository stream query in a widget test must go through
        // `tester.runAsync` — see `meals_screen_test.dart`'s comment.
        expect(
          await tester.runAsync(() => recipes.watchSaved('test-user').first),
          isEmpty,
        );
        // Whether this pops (a prior page beneath it) or falls back to
        // `go(pantry)` (nothing to pop), either way this recipe's own
        // detail screen must not still be showing.
        expect(
          find.descendant(
            of: find.byType(AppBar),
            matching: find.text('Lentil Soup'),
          ),
          findsNothing,
        );
      },
    );

    testWidgets(
      'the outer loading→content hand-off goes through GleanCrossFade, not '
      'a hard cut (R-14, AC-TRN-01)',
      (WidgetTester tester) async {
        final int id = await recipes.save(
          userId: 'test-user',
          externalId: 'ext-4',
          title: 'Tomato Soup',
          ingredients: const <SaveRecipeIngredient>[],
        );

        await harness.pumpAt(tester, AppRoutes.mealsDetailPath('$id'));
        // Present in the tree wrapping whichever state is current — this is
        // the mechanism itself, not a frame-timing assertion (the previous
        // bare `.when()` had no equivalent widget to find here at all). At
        // least one: this outer instance, possibly plus
        // `_SavedRecipeDetailBody`'s own separate one for the ingredients
        // list, depending on how far the in-memory streams have resolved by
        // this point.
        expect(find.byType(GleanCrossFade), findsAtLeastNWidgets(1));

        await tester.pumpAndSettle();
        expect(find.text('Tomato Soup'), findsOneWidget);
        // Two now: this outer one plus `_SavedRecipeDetailBody`'s own,
        // separate cross-fade for the ingredients list — both legitimate,
        // not a regression of this test's own making.
        expect(find.byType(GleanCrossFade), findsNWidgets(2));
      },
    );

    testWidgets('a missing recipe shows a recoverable error, not a spinner', (
      WidgetTester tester,
    ) async {
      await harness.pumpAt(tester, AppRoutes.mealsDetailPath('999'));
      await tester.pumpAndSettle();

      expect(find.byType(RouteErrorScreen), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);

      await tester.tap(find.widgetWithText(FilledButton, 'Back to Pantry'));
      await tester.pumpAndSettle();

      // Recovered to *something* other than the permanent-spinner dead end
      // the RN app hit here (§11) — not necessarily a specific screen,
      // since whether this pops or falls back to `go(pantry)` depends on
      // go_router's stacking of the parent `/meals` route beneath it.
      expect(find.byType(RouteErrorScreen), findsNothing);
    });
  });
}
