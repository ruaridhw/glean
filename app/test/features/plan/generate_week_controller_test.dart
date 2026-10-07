// Replaces obsolete saved-only responses with Plan -> corpus -> detail -> DB.
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/router/app_routes.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import '../../support/harness.dart';

Map<String, Object?> pick(String id) => {
  'recipe_id': null,
  'external_id': id,
  'title': 'Corpus $id',
  'reason': 'fit',
};
http.Response proposal(List<Map<String, Object?>> picks) =>
    http.Response(jsonEncode({'suggestions': picks}), 200);
http.Response detail(String id) => http.Response(
  jsonEncode({
    'external_id': id,
    'title': 'Corpus $id',
    'ingredients': [
      {'canonical_name': 'beans', 'quantity': 200, 'unit': 'g'},
    ],
  }),
  200,
);

void main() {
  gleanWidgetTest(
    'Plan Generate honors corpus settings and exclusions then persists recipes, servings and aggregated demand',
    (tester) async {
      Map<String, dynamic>? body;
      final h = AppTestHarness(
        httpClient: MockClient((request) async {
          if (request.method == 'POST') {
            body = jsonDecode(request.body) as Map<String, dynamic>;
            return proposal([
              pick('rec_a'),
              pick('rec_b'),
              pick('rec_existing'),
            ]);
          }
          return detail(request.url.pathSegments.last);
        }),
      );
      addTearDown(h.dispose);
      final recipes = h.container.read(recipesRepositoryProvider);
      final plan = h.container.read(planRepositoryProvider);
      final existing = await recipes.save(
        userId: h.userId,
        externalId: 'rec_existing',
        title: 'Existing',
        ingredients: const [],
      );
      await plan.addEntry(
        userId: h.userId,
        recipeId: existing,
        recipeTitle: 'Existing',
        servings: 1,
      );
      await h.container
          .read(userConfigRepositoryProvider)
          .save(
            UserConfigView(
              id: h.userId,
              purchaseTolerance: 0.25,
              preferredServings: 3,
              mealsPerWeek: 3,
              dietaryFlags: const ['vegetarian'],
              maxActiveTimeMins: 30,
            ),
          );
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
      await tester.pumpAndSettle();
      expect(body!['source'], 'corpus');
      expect(body!['exclude_external_ids'], contains('rec_existing'));
      expect(body!['purchase_tolerance'], 0.25);
      expect(body!['dietary_flags'], ['vegetarian']);
      expect(body!['max_active_time_mins'], 30);
      expect(body!['meals_per_week'], 2);
      expect(find.text('Corpus rec_a'), findsOneWidget);
      expect(find.text('Corpus rec_b'), findsOneWidget);
      final entries = await tester.runAsync(
        () => plan.getWeek(
          userId: h.userId,
          weekStart: startOfWeek(DateTime.now()),
        ),
      );
      expect(entries, hasLength(3));
      expect(
        entries!.where((e) => e.recipeId != existing).map((e) => e.servings),
        everyElement(3),
      );
      expect(
        await tester.runAsync(() => recipes.getSaved(h.userId)),
        hasLength(3),
      );
      expect(
        (await tester.runAsync(
          () => h.container
              .read(shoppingRepositoryProvider)
              .watchAll(h.userId)
              .first,
        ))!.single.quantity,
        1200,
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('shopping list'), findsOneWidget);
    },
  );
  gleanWidgetTest(
    'all failed corpus details leave no half-plan and a visible retry succeeds',
    (tester) async {
      var fail = true;
      final h = AppTestHarness(
        httpClient: MockClient(
          (request) async => request.method == 'POST'
              ? proposal([pick('rec_a')])
              : fail
              ? http.Response('{}', 500)
              : detail('rec_a'),
        ),
      );
      addTearDown(h.dispose);
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
      await tester.pumpAndSettle();
      expect(find.text('No recipes fit right now. Try again.'), findsOneWidget);
      final plan = h.container.read(planRepositoryProvider);
      expect(
        await tester.runAsync(
          () => plan.getWeek(
            userId: h.userId,
            weekStart: startOfWeek(DateTime.now()),
          ),
        ),
        isEmpty,
      );
      fail = false;
      await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
      await tester.pumpAndSettle();
      expect(find.text('Corpus rec_a'), findsOneWidget);
      expect(
        await tester.runAsync(
          () => plan.getWeek(
            userId: h.userId,
            weekStart: startOfWeek(DateTime.now()),
          ),
        ),
        hasLength(1),
      );
    },
  );
}
