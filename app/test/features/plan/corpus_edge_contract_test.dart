import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
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
import '../../support/session_backend.dart';

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
          httpClient: sessionRoutes((request) async {
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
        if (find.text('Add 1 dinner to plan').evaluate().isNotEmpty) {
          await tester.tap(find.text('Add 1 dinner to plan'));
          await tester.pumpAndSettle();
        }
        expect(
          find
                  .text('Something went wrong planning your week.')
                  .evaluate()
                  .isNotEmpty ||
              find.text('No meals to suggest').evaluate().isNotEmpty,
          isTrue,
          reason: 'the proposal screen explains the failure in approved copy',
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
        await tester.tap(find.text('Close'));
        await tester.pumpAndSettle();
        bad = false;
        await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Add 1 dinner to plan'));
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
    'a rate-limited generation says the hourly limit was reached',
    (tester) async {
      final h = AppTestHarness(
        httpClient: MockClient(
          (request) async => http.Response(
            jsonEncode({'detail': 'AI request limit reached'}),
            429,
          ),
        ),
      );
      addTearDown(h.dispose);
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
      await tester.pumpAndSettle();

      expect(
        find.text("You've used too many AI credits. Try again in 60 minutes."),
        findsOneWidget,
      );
      expect(find.text('Nothing was added to your plan.'), findsOneWidget);
      // rate_limited offers nothing: retrying straight away fails the same way.
      expect(find.text('Retry'), findsNothing);
    },
  );
  gleanWidgetTest(
    'detail persistence failure leaves no plan/gaps and retry safely reuses already saved details',
    (tester) async {
      final h = AppTestHarness(
        httpClient: sessionRoutes(
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
      await tester.tap(find.text('Add 2 dinners to plan'));
      await tester.pumpAndSettle();
      expect(
        find.text('Something went wrong planning your week.'),
        findsOneWidget,
      );
      expect(find.text('Nothing was added to your plan.'), findsOneWidget);
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
      await tester.tap(find.text('Retry'));
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
  test(
    'a manual add while generation runs cannot duplicate a recipe or exceed fresh capacity',
    () async {
      final seen = Completer<void>();
      final response = Completer<http.Response>();
      var creates = 0;
      final h = AppTestHarness(
        httpClient: sessionRoutes((request) {
          if (request.method == 'POST') {
            creates++;
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
      final controller = h.container.read(
        generateWeekControllerProvider.notifier,
      );
      final generation = controller.generate(
        weekStart: week,
        slots: 3,
        servings: 1,
      );
      await seen.future;
      // A second Generate tap while the first is still running cannot open another session.
      await controller.generate(weekStart: week, slots: 3, servings: 1);
      expect(creates, 1);
      // The user adds a dinner by hand while the review's session is still queued.
      await h.container
          .read(planRepositoryProvider)
          .addEntry(
            userId: h.userId,
            recipeId: r,
            recipeTitle: 'Manual',
            servings: 1,
            plannedDate: week,
          );
      response.complete(
        proposal([pick('rec_a'), pick('rec_b'), pick('rec_c')]),
      );
      await generation;
      expect(
        h.container.read(generateWeekControllerProvider).phase,
        GenerateProposalPhase.proposal,
      );
      await controller.addToPlan();
      final entries = await h.container
          .read(planRepositoryProvider)
          .getWeek(userId: h.userId, weekStart: week);
      expect(entries, hasLength(3));
      expect(entries.map((entry) => entry.recipeId).toSet(), hasLength(3));
      expect(entries.where((entry) => entry.recipeId == r), hasLength(1));
    },
  );
}
