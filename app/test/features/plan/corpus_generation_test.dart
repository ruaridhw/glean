import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/router/app_routes.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/features/plan/providers/generate_week_controller.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';

import '../../support/harness.dart';

class MockCorpusHttp extends Mock implements http.Client {}

void main() {
  setUpAll(() => registerFallbackValue(Uri.parse('http://localhost/')));
  final week = DateTime(2026, 10, 5);
  late MockCorpusHttp client;
  late AppTestHarness harness;
  setUp(() {
    client = MockCorpusHttp();
    harness = AppTestHarness(httpClient: client);
  });
  tearDown(() => harness.dispose());

  void suggest(
    List<String> ids, {
    void Function(Map<String, dynamic>)? capture,
  }) {
    when(
      () => client.post(
        any(),
        headers: any(named: 'headers'),
        body: any(named: 'body'),
      ),
    ).thenAnswer((call) async {
      capture?.call(
        jsonDecode(call.namedArguments[#body] as String)
            as Map<String, dynamic>,
      );
      return http.Response(
        jsonEncode({
          'suggestions': [
            for (final id in ids)
              {
                'recipe_id': null,
                'external_id': id,
                'title': id,
                'reason': 'Pantry fit',
              },
          ],
        }),
        200,
      );
    });
  }

  void detail(String id, {int status = 200}) {
    when(
      () => client.get(
        any(that: predicate<Uri>((uri) => uri.path.endsWith('/$id'))),
        headers: any(named: 'headers'),
      ),
    ).thenAnswer(
      (_) async => http.Response(
        jsonEncode({
          'external_id': id,
          'title': 'Corpus $id',
          'yield_count': 2,
          'ingredients': [
            {'canonical_name': 'beans', 'quantity': 200, 'unit': 'g'},
          ],
        }),
        status,
      ),
    );
  }

  test(
    'corpus wire response accepts null recipe id without missing ingredients',
    () {
      final response = MealPlanResponse.fromJson({
        'suggestions': [
          {
            'recipe_id': null,
            'external_id': 'rec_1',
            'title': 'Beans',
            'reason': 'Fit',
          },
        ],
      });
      expect(response.suggestions.single.recipeId, isNull);
    },
  );

  test(
    'fetches corpus picks, skips failed detail, reuses saved recipes and excludes planned external ids',
    () async {
      final recipes = harness.container.read(recipesRepositoryProvider);
      final plan = harness.container.read(planRepositoryProvider);
      final savedId = await recipes.save(
        userId: harness.userId,
        externalId: 'rec_saved',
        title: 'Saved beans',
        ingredients: const [],
      );
      final plannedId = await recipes.save(
        userId: harness.userId,
        externalId: 'rec_planned',
        title: 'Already planned',
        ingredients: const [],
      );
      await plan.addEntry(
        userId: harness.userId,
        recipeId: plannedId,
        recipeTitle: 'Already planned',
        servings: 2,
        plannedDate: week,
      );
      Map<String, dynamic>? body;
      suggest([
        'rec_bad',
        'rec_new',
        'rec_saved',
      ], capture: (value) => body = value);
      detail('rec_bad', status: 404);
      detail('rec_new');
      await harness.container
          .read(generateWeekControllerProvider.notifier)
          .generate(weekStart: week, slots: 3, servings: 4);
      expect(
        harness.container.read(generateWeekControllerProvider).hasError,
        isFalse,
        reason:
            '${harness.container.read(generateWeekControllerProvider).error}',
      );
      expect(body!['source'], 'corpus');
      expect(body!['exclude_external_ids'], ['rec_planned']);
      expect(body!['meals_per_week'], 3);
      final entries = await plan.getWeek(
        userId: harness.userId,
        weekStart: week,
      );
      expect(entries, hasLength(3));
      expect(entries.where((e) => e.recipeId == savedId).single.servings, 4);
      expect(await recipes.getSaved(harness.userId), hasLength(3));
      final gaps = await harness.container
          .read(shoppingRepositoryProvider)
          .watchAll(harness.userId)
          .first;
      expect(gaps.single.name, 'beans');
      expect(gaps.single.quantity, 800); // Existing per-serving gap semantics.
    },
  );

  test(
    'pending spans detail fetch and duplicate picks never overfill',
    () async {
      suggest(['rec_new', 'rec_new']);
      final pending = Completer<http.Response>();
      when(
        () => client.get(any(), headers: any(named: 'headers')),
      ).thenAnswer((_) => pending.future);
      final controller = harness.container.read(
        generateWeekControllerProvider.notifier,
      );
      final operation = controller.generate(
        weekStart: week,
        slots: 2,
        servings: 2,
      );
      await Future<void>.delayed(const Duration(milliseconds: 50));
      await harness.container.pump();
      expect(
        harness.container.read(generateWeekControllerProvider).isLoading,
        isTrue,
      );
      await controller.generate(weekStart: week, slots: 2, servings: 2);
      pending.complete(
        http.Response(
          jsonEncode({'external_id': 'rec_new', 'title': 'Beans'}),
          200,
        ),
      );
      await operation;
      final entries = await harness.container
          .read(planRepositoryProvider)
          .getWeek(userId: harness.userId, weekStart: week);
      expect(entries, hasLength(1));
    },
  );

  gleanWidgetTest('zero corpus picks show retry feedback, never success', (
    tester,
  ) async {
    suggest([]);
    await harness.pumpAt(tester, AppRoutes.plan.path);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
    await pumpUntil(
      tester,
      () => find
          .text('No recipes fit right now. Try again.')
          .evaluate()
          .isNotEmpty,
      description: 'empty-generation feedback',
    );
    expect(find.text('Week generated'), findsNothing);
  });

  test('a gap insertion failure rolls back all plan entries', () async {
    suggest(['rec_new']);
    detail('rec_new');
    await harness.db.customStatement(
      "CREATE TRIGGER fail_gaps BEFORE INSERT ON shopping_list_items BEGIN SELECT RAISE(ABORT, 'gap failure'); END",
    );
    await harness.container
        .read(generateWeekControllerProvider.notifier)
        .generate(weekStart: week, slots: 1, servings: 2);
    expect(
      harness.container.read(generateWeekControllerProvider).hasError,
      isTrue,
    );
    final entries = await harness.container
        .read(planRepositoryProvider)
        .getWeek(userId: harness.userId, weekStart: week);
    expect(entries, isEmpty);
    expect(
      await harness.container
          .read(recipesRepositoryProvider)
          .getSaved(harness.userId),
      hasLength(1),
    );
  });
}
