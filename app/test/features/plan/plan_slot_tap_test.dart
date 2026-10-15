// A filled Plan slot opens its recipe inside the Plan tab. Real router and SQLite; only the HTTP client is faked.
import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_test/flutter_test.dart';
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
  final requestedPaths = <String>[];

  AppTestHarness build({int previewStatus = 200, Future<void>? gate}) =>
      AppTestHarness(
        httpClient: MockClient((http.Request request) async {
          await gate;
          requestedPaths.add(request.url.path);
          if (request.url.path == '/recipes/ext-1' && previewStatus == 200) {
            return http.Response(
              jsonEncode(<String, dynamic>{
                'external_id': 'ext-1',
                'title': 'Miso Soup',
                'source_url': null,
                'cuisine': null,
                'difficulty': null,
                'active_time_mins': null,
                'total_time_mins': null,
                'dietary_flags': <String>[],
                'not_suitable_for': <String>[],
                'yield_count': 2,
                'nutrition': null,
                'instructions': <Map<String, dynamic>>[],
                'ingredients': <Map<String, dynamic>>[],
              }),
              200,
              headers: <String, String>{'content-type': 'application/json'},
            );
          }
          return http.Response('not found', 404);
        }),
      );

  setUp(() {
    requestedPaths.clear();
    h = build();
  });
  tearDown(() => h.dispose());

  Future<int> plannedMeal(
    String title, {
    String? externalId,
    DateTime? date,
  }) async {
    final recipeId = await h.container
        .read(recipesRepositoryProvider)
        .save(
          userId: h.userId,
          externalId: externalId,
          title: title,
          ingredients: const <SaveRecipeIngredient>[],
        );
    await h.container
        .read(planRepositoryProvider)
        .addEntry(
          userId: h.userId,
          recipeId: recipeId,
          recipeTitle: title,
          servings: 1,
          plannedDate: date ?? week,
        );
    return recipeId;
  }

  Future<void> openPlan(WidgetTester tester) async {
    await h.pumpAt(tester, AppRoutes.plan.path);
    await tester.pumpAndSettle();
  }

  // A pushed route is not reflected in `routeInformationProvider`; the router's configuration tracks it.
  String location() =>
      h.router.routerDelegate.currentConfiguration.last.matchedLocation;

  gleanWidgetTest(
    'tapping a planned meal opens its recipe and Back returns to the same week',
    (tester) async {
      final nextWeek = week.add(const Duration(days: 7));
      final recipeId = await plannedMeal('Lentil Dal', date: nextWeek);
      await openPlan(tester);
      await tester.tap(find.byTooltip('Next week'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Lentil Dal'));
      await tester.pumpAndSettle();

      expect(location(), AppRoutes.planRecipePath('$recipeId'));
      expect(
        find.descendant(
          of: find.byType(AppBar),
          matching: find.text('Lentil Dal'),
        ),
        findsOneWidget,
      );

      await tester.pageBack();
      await tester.pumpAndSettle();

      expect(location(), AppRoutes.plan.path);
      expect(find.text('Lentil Dal'), findsOneWidget);
      expect(find.text('Dinners'), findsOneWidget);
      expect(find.byTooltip('Previous week'), findsOneWidget);
    },
  );

  gleanWidgetTest('Cooked? marks the meal cooked without opening the recipe', (
    tester,
  ) async {
    await plannedMeal('Lentil Dal');
    await openPlan(tester);

    await tester.tap(find.widgetWithText(OutlinedButton, 'Cooked?'));
    await tester.pumpAndSettle();

    expect(location(), AppRoutes.plan.path);
    expect(find.widgetWithText(OutlinedButton, 'Cooked?'), findsNothing);
    expect(find.textContaining('Cooked'), findsWidgets);
    expect(find.text('Dinners'), findsOneWidget);
  });

  gleanWidgetTest(
    'a planned meal whose recipe was deleted opens the preview from its external id',
    (tester) async {
      final recipeId = await plannedMeal('Miso Soup', externalId: 'ext-1');
      await h.container
          .read(recipesRepositoryProvider)
          .deleteRecipe(id: recipeId, userId: h.userId);
      await openPlan(tester);

      await tester.tap(find.text('Miso Soup'));
      await tester.pumpAndSettle();

      expect(requestedPaths, contains('/recipes/ext-1'));
      expect(find.byTooltip('Save recipe'), findsOneWidget);
      expect(find.text('Dinners'), findsNothing);

      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('Dinners'), findsOneWidget);
    },
  );

  group('when the snapshot does not resolve', () {
    setUp(() async {
      await h.dispose();
      h = build(previewStatus: 404);
    });

    gleanWidgetTest(
      'a deleted recipe whose snapshot will not load says Recipe removed and stays on Plan',
      (tester) async {
        final recipeId = await plannedMeal('Old Import', externalId: 'ext-1');
        await h.container
            .read(recipesRepositoryProvider)
            .deleteRecipe(id: recipeId, userId: h.userId);
        await openPlan(tester);

        await tester.tap(find.text('Old Import'));
        await tester.pumpAndSettle();

        expect(requestedPaths, contains('/recipes/ext-1'));
        expect(find.text('Recipe removed'), findsOneWidget);
        expect(find.byTooltip('Save recipe'), findsNothing);
        expect(location(), AppRoutes.plan.path);
        expect(find.text('Dinners'), findsOneWidget);
      },
    );
  });

  gleanWidgetTest(
    'a planned meal with no recipe and no snapshot is not tappable',
    (tester) async {
      final recipeId = await plannedMeal('Orphan Dinner');
      await h.container
          .read(recipesRepositoryProvider)
          .deleteRecipe(id: recipeId, userId: h.userId);
      final semantics = tester.ensureSemantics();
      await openPlan(tester);

      expect(
        tester
            .getSemantics(find.text('Orphan Dinner'))
            .getSemanticsData()
            .hasAction(SemanticsAction.tap),
        isFalse,
      );
      semantics.dispose();
      await tester.tap(find.text('Orphan Dinner'));
      await tester.pumpAndSettle();

      expect(requestedPaths, isEmpty);
      expect(location(), AppRoutes.plan.path);
      expect(find.text('Dinners'), findsOneWidget);
      expect(find.byTooltip('Save recipe'), findsNothing);
    },
  );

  gleanWidgetTest(
    'tapping a planned meal again during a slow preview lookup opens one preview',
    (tester) async {
      await h.dispose();
      final lookup = Completer<void>();
      h = build(gate: lookup.future);
      final recipeId = await plannedMeal('Miso Soup', externalId: 'ext-1');
      await h.container
          .read(recipesRepositoryProvider)
          .deleteRecipe(id: recipeId, userId: h.userId);
      await openPlan(tester);

      await tester.tap(find.text('Miso Soup'));
      await tester.pump();
      await tester.tap(find.text('Miso Soup'));
      await tester.pump();
      lookup.complete();
      await tester.pumpAndSettle();
      expect(find.byTooltip('Save recipe'), findsOneWidget);

      await tester.pageBack();
      await tester.pumpAndSettle();

      expect(find.byTooltip('Save recipe'), findsNothing);
      expect(find.text('Dinners'), findsOneWidget);
    },
  );
}
