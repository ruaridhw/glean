import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/router/app_routes.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/meal_thumb.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/util/week.dart';
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

  test('sends each cook\'s rating and note, and a cleared rating as null', () async {
    final recipes = harness.container.read(recipesRepositoryProvider);
    final plan = harness.container.read(planRepositoryProvider);
    final now = DateTime.now();
    Future<int> cooked(String externalId, String title) async {
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
        plannedDate: now.subtract(const Duration(days: 10)),
      );
      await plan.markCooked(
        entryId: entryId,
        userId: harness.userId,
        now: now.subtract(const Duration(days: 10)),
      );
      return entryId;
    }

    final disliked = await cooked('rec_down', 'Disliked stew');
    await plan.rateWithNote(
      entryId: disliked,
      userId: harness.userId,
      rating: MealThumb.down,
      note: 'too sweet for the kids',
    );
    final liked = await cooked('rec_up', 'Liked pie');
    await plan.rate(
      entryId: liked,
      userId: harness.userId,
      rating: MealThumb.up,
    );
    // Cooked, once rated, then cleared: the entry stays in the history window unrated.
    final cleared = await cooked('rec_cleared', 'Cleared soup');
    await plan.rate(
      entryId: cleared,
      userId: harness.userId,
      rating: MealThumb.down,
    );
    await plan.clearRating(entryId: cleared, userId: harness.userId);
    // A comment written as 250 combining pairs: 500 code points, one per visible character, right at the
    // wire bound. Both sides measure code points, so this request still validates.
    final combiningEntry = await cooked('rec_combining', 'Combining soup');
    await plan.rateWithNote(
      entryId: combiningEntry,
      userId: harness.userId,
      rating: MealThumb.down,
      note: 'e\u0301' * 250,
    );

    Map<String, dynamic>? body;
    suggest(['rec_new'], capture: (value) => body = value);
    detail('rec_new');

    await harness.container
        .read(generateWeekControllerProvider.notifier)
        .generate(weekStart: week, slots: 1, servings: 2);

    final history = <String, Map<String, dynamic>>{
      for (final item
          in (body!['cooked_history'] as List).cast<Map<String, dynamic>>())
        item['recipe_id'] as String: item,
    };
    expect(ratingNoteLength(history['rec_combining']!['note'] as String), 500);
    expect(history['rec_down']!['rating'], 'down');
    expect(history['rec_down']!['note'], 'too sweet for the kids');
    expect(history['rec_up']!['rating'], 'up');
    expect(history['rec_up']!['note'], isNull);
    expect(history['rec_cleared']!['rating'], isNull);
    expect(history['rec_cleared']!['note'], isNull);
  });

  test(
    'sends a thumbs down however old its cook is, so the dislike never expires',
    () async {
      final recipes = harness.container.read(recipesRepositoryProvider);
      final plan = harness.container.read(planRepositoryProvider);
      final now = DateTime.now();
      Future<int> cooked(
        String externalId,
        String title, {
        required int daysAgo,
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
          plannedDate: now.subtract(Duration(days: daysAgo)),
        );
        await plan.markCooked(
          entryId: entryId,
          userId: harness.userId,
          now: now.subtract(Duration(days: daysAgo)),
        );
        return entryId;
      }

      // Twenty weeks old: outside the twelve-week window, so only the thumb carries it.
      final disliked = await cooked('rec_old', 'Old dislike', daysAgo: 140);
      await plan.rateWithNote(
        entryId: disliked,
        userId: harness.userId,
        rating: MealThumb.down,
        note: 'not again',
      );
      final withinWindow = await cooked('rec_recent', 'Recent', daysAgo: 10);

      Map<String, dynamic>? body;
      suggest(['rec_new'], capture: (value) => body = value);
      detail('rec_new');

      await harness.container
          .read(generateWeekControllerProvider.notifier)
          .generate(weekStart: week, slots: 1, servings: 2);

      final history = <String, Map<String, dynamic>>{
        for (final item
            in (body!['cooked_history'] as List).cast<Map<String, dynamic>>())
          item['recipe_id'] as String: item,
      };
      expect(history.keys, containsAll(<String>['rec_old', 'rec_recent']));
      expect(history['rec_old']!['rating'], 'down');
      expect(history['rec_old']!['note'], 'not again');
      expect(
        DateTime.parse(history['rec_old']!['cooked_at'] as String),
        now.subtract(const Duration(days: 140)).toUtc(),
      );

      // Clearing the thumb stops the old cook travelling: the window alone is sent.
      await plan.clearRating(entryId: disliked, userId: harness.userId);
      await harness.container
          .read(generateWeekControllerProvider.notifier)
          .generate(weekStart: week, slots: 1, servings: 2);

      final clearedIds = <String>{
        for (final item
            in (body!['cooked_history'] as List).cast<Map<String, dynamic>>())
          item['recipe_id'] as String,
      };
      expect(clearedIds, contains('rec_recent'));
      expect(clearedIds, isNot(contains('rec_old')));
      expect(withinWindow, isNotNull);
    },
  );

  test(
    'sends the phone local date, so a going-off item is dated in the household calendar',
    () async {
      // The backend cannot derive which calendar date `expires_in_days` was measured from, and the
      // servers UTC date is a day behind a UK phone late in the evening.
      final now = DateTime.now();
      Map<String, dynamic>? body;
      suggest(['rec_new'], capture: (value) => body = value);
      detail('rec_new');

      await harness.container
          .read(generateWeekControllerProvider.notifier)
          .generate(weekStart: week, slots: 1, servings: 2);

      expect(body!['local_date'], formatDate(now));
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
