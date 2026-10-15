import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/features/plan/providers/generate_week_controller.dart';
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
  for (final malformed in <Map<String, Object?>>[
    {'external_id': 7, 'title': 'Bad'},
    {'title': 'Missing identity'},
    {'external_id': '', 'title': 'Blank'},
  ]) {
    gleanWidgetTest(
      'invalid corpus identity ${malformed['external_id']} is recoverable without half-writes',
      (tester) async {
        var bad = true;
        final h = AppTestHarness(
          httpClient: MockClient((request) async {
            if (request.method == 'POST') {
              return proposal(bad ? [malformed] : [pick('rec_ok')]);
            }
            return bad ? http.Response('{}', 404) : detail('rec_ok');
          }),
        );
        addTearDown(h.dispose);
        await h.pumpAt(tester, AppRoutes.plan.path);
        await tester.pumpAndSettle();
        await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
        await tester.pumpAndSettle();
        expect(
          find.text('Could not generate meal plan.').evaluate().isNotEmpty ||
              find
                  .text('No recipes fit right now. Try again.')
                  .evaluate()
                  .isNotEmpty,
          isTrue,
        );
        final plan = h.container.read(planRepositoryProvider);
        final week = startOfWeek(DateTime.now());
        expect(
          await tester.runAsync(
            () => plan.getWeek(userId: h.userId, weekStart: week),
          ),
          isEmpty,
        );
        expect(
          await tester.runAsync(
            () => h.container
                .read(shoppingRepositoryProvider)
                .watchAll(h.userId)
                .first,
          ),
          isEmpty,
        );
        bad = false;
        await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
        await tester.pumpAndSettle();
        expect(
          await tester.runAsync(
            () => plan.getWeek(userId: h.userId, weekStart: week),
          ),
          hasLength(1),
        );
      },
    );
  }
  gleanWidgetTest(
    'detail persistence failure leaves no plan/gaps and retry safely reuses already saved details',
    (tester) async {
      final h = AppTestHarness(
        httpClient: MockClient(
          (request) async => request.method == 'POST'
              ? proposal([pick('rec_a'), pick('rec_b')])
              : detail(request.url.pathSegments.last),
        ),
      );
      addTearDown(h.dispose);
      await h.db.customStatement(
        "CREATE TRIGGER fail_recipe BEFORE INSERT ON recipes WHEN NEW.title='Corpus rec_b' BEGIN SELECT RAISE(ABORT, 'test failure'); END",
      );
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
      await tester.pumpAndSettle();
      expect(find.text('Could not generate meal plan.'), findsOneWidget);
      final plan = h.container.read(planRepositoryProvider);
      final week = startOfWeek(DateTime.now());
      expect(
        await tester.runAsync(
          () => plan.getWeek(userId: h.userId, weekStart: week),
        ),
        isEmpty,
      );
      expect(
        await tester.runAsync(
          () => h.container
              .read(shoppingRepositoryProvider)
              .watchAll(h.userId)
              .first,
        ),
        isEmpty,
      );
      expect(
        await tester.runAsync(
          () => h.container.read(recipesRepositoryProvider).getSaved(h.userId),
        ),
        hasLength(1),
      );
      await tester.runAsync(
        () => h.db.customStatement('DROP TRIGGER fail_recipe'),
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
      await tester.pumpAndSettle();
      expect(
        await tester.runAsync(
          () => plan.getWeek(userId: h.userId, weekStart: week),
        ),
        hasLength(2),
      );
      expect(
        await tester.runAsync(
          () => h.container.read(recipesRepositoryProvider).getSaved(h.userId),
        ),
        hasLength(2),
      );
    },
  );
  gleanWidgetTest(
    'manual double-tap overlapping Generate cannot duplicate a recipe or exceed fresh capacity',
    (tester) async {
      final seen = Completer<void>();
      final response = Completer<http.Response>();
      final h = AppTestHarness(
        httpClient: MockClient((request) {
          if (request.method == 'POST') {
            seen.complete();
            return response.future;
          }
          return Future.value(detail(request.url.pathSegments.last));
        }),
      );
      addTearDown(h.dispose);
      await h.container
          .read(userConfigRepositoryProvider)
          .save(
            UserConfigView(
              id: h.userId,
              purchaseTolerance: 0.5,
              preferredServings: 1,
              mealsPerWeek: 3,
              dietaryFlags: const [],
              maxActiveTimeMins: null,
            ),
          );
      final r = await h.container
          .read(recipesRepositoryProvider)
          .save(
            userId: h.userId,
            externalId: 'rec_a',
            title: 'Manual',
            ingredients: const [
              SaveRecipeIngredient(
                canonicalName: 'beans',
                quantity: 200,
                unit: 'g',
              ),
            ],
          );
      final week = startOfWeek(DateTime.now());
      final generation = h.container
          .read(generateWeekControllerProvider.notifier)
          .generate(weekStart: week, slots: 3, servings: 1);
      await seen.future;
      await h.pumpAt(tester, AppRoutes.mealsDetailPath('$r'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Add to plan'));
      await tester.tap(find.widgetWithText(FilledButton, 'Add to plan'));
      await tester.pumpAndSettle();
      final plan = h.container.read(planRepositoryProvider);
      expect(
        await tester.runAsync(
          () => plan.getWeek(userId: h.userId, weekStart: week),
        ),
        hasLength(1),
      );
      response.complete(
        proposal([pick('rec_a'), pick('rec_b'), pick('rec_c')]),
      );
      await pumpUntil(
        tester,
        () => !h.container.read(generateWeekControllerProvider).isLoading,
        description: 'generation after manual add',
      );
      await generation;
      await tester.pumpAndSettle();
      final entries = await tester.runAsync(
        () => plan.getWeek(userId: h.userId, weekStart: week),
      );
      expect(entries, hasLength(3));
      expect(entries!.map((e) => e.recipeId).toSet(), hasLength(3));
      expect(entries.where((e) => e.recipeId == r), hasLength(1));
    },
  );
}
