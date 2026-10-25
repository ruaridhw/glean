import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/router/app_routes.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
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
      // The API supplies 200g for a two-serving recipe; requesting four
      // servings needs 400g, not the old per-serving assumption of 800g.
      expect(gaps.single.quantity, 400);
    },
  );

  test(
    'sends the last twelve weeks of cooked meals, and nothing else',
    () async {
      final recipes = harness.container.read(recipesRepositoryProvider);
      final plan = harness.container.read(planRepositoryProvider);
      final now = DateTime.now();
      Future<void> planned(
        String externalId,
        String title, {
        DateTime? cookedAt,
      }) async {
        final recipeId = await recipes.save(
          userId: harness.userId,
          externalId: externalId,
          title: title,
          ingredients: const [],
        );
        final entryId = await plan.addEntry(
          userId: harness.userId,
          recipeId: recipeId,
          recipeTitle: title,
          servings: 2,
          plannedDate: cookedAt ?? now,
        );
        if (cookedAt != null) {
          await plan.markCooked(
            entryId: entryId,
            userId: harness.userId,
            now: cookedAt,
          );
        }
      }

      final recentCook = now.subtract(const Duration(days: 10));
      await planned('rec_recent', 'Recent stew', cookedAt: recentCook);
      await planned(
        'rec_stale',
        'Stale pie',
        cookedAt: now.subtract(const Duration(days: 90)),
      );
      await planned('rec_uncooked', 'Never cooked');
      Map<String, dynamic>? body;
      suggest(['rec_new'], capture: (value) => body = value);
      detail('rec_new');

      await harness.container
          .read(generateWeekControllerProvider.notifier)
          .generate(weekStart: week, slots: 3, servings: 2);

      final history = (body!['cooked_history'] as List)
          .cast<Map<String, dynamic>>();
      expect(history, hasLength(1));
      expect(history.single['recipe_id'], 'rec_recent');
      expect(history.single['title'], 'Recent stew');
      expect(
        DateTime.parse(history.single['cooked_at'] as String),
        recentCook.toUtc(),
      );
    },
  );

  test(
    'sends cooked times as UTC instants, so a local wall clock keeps its age',
    () async {
      final recipes = harness.container.read(recipesRepositoryProvider);
      final plan = harness.container.read(planRepositoryProvider);
      // A cook recorded in local time: the plan entry stores it with no offset. Read as UTC by the
      // server, a 41d23h-old cook in a UTC-7 zone looked fresh, so the request must state the zone.
      // Ten days back, because Generate sends a live twelve-week window.
      final today = DateTime.now();
      final localCook = DateTime(
        today.year,
        today.month,
        today.day,
        18,
        30,
      ).subtract(const Duration(days: 10));
      final recipeId = await recipes.save(
        userId: harness.userId,
        externalId: 'rec_local',
        title: 'Local stew',
        ingredients: const [],
      );
      final entryId = await plan.addEntry(
        userId: harness.userId,
        recipeId: recipeId,
        recipeTitle: 'Local stew',
        servings: 2,
        plannedDate: localCook,
      );
      await plan.markCooked(
        entryId: entryId,
        userId: harness.userId,
        now: localCook,
      );
      Map<String, dynamic>? body;
      suggest(['rec_new'], capture: (value) => body = value);
      detail('rec_new');

      await harness.container
          .read(generateWeekControllerProvider.notifier)
          .generate(weekStart: week, slots: 1, servings: 2);

      final history = (body!['cooked_history'] as List)
          .cast<Map<String, dynamic>>();
      final sent = history.single['cooked_at'] as String;
      expect(sent, endsWith('Z'));
      expect(DateTime.parse(sent).isAtSameMomentAs(localCook), isTrue);
      expect(DateTime.parse(sent), localCook.toUtc());
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
    expect(find.textContaining('Week generated'), findsNothing);
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
