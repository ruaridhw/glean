// The V3 proposal screen, one test per state in the gate's direction A: working with progress, proposal,
// swap/unswap, a planned meal greyed and swappable, no meals, partial week, degraded indistinguishable, cancel
// and back discarding. Nothing is written before Add to plan, and Add is one transaction.
import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/meal_thumb.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/features/plan/providers/generate_week_controller.dart';
import 'package:glean/features/plan/widgets/proposal_meal_card.dart';
import 'package:glean/router/app_routes.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../support/harness.dart';
import '../../support/session_backend.dart';

Map<String, dynamic> suggestion(
  String id, {
  required String title,
  required String reason,
  String? reasonKind,
  Map<String, dynamic>? alternative,
}) => <String, dynamic>{
  'recipe_id': null,
  'external_id': id,
  'title': title,
  'reason': reason,
  'reason_kind': ?reasonKind,
  'uses_up': <Map<String, dynamic>>[],
  'alternative': alternative,
};

Map<String, dynamic> alternative(String id, String title) => <String, dynamic>{
  'recipe_id': null,
  'external_id': id,
  'title': title,
  'reason': 'The other one: $title',
};

const Map<String, String> _detailTitles = <String, String>{
  'rec_a': 'Chicken katsu curry',
  'rec_b': 'Black bean tacos',
  'rec_a_alt': 'Chicken & cashew stir-fry',
  'rec_b_alt': 'Chickpea & spinach dal',
  'rec_planned_alt': 'Fish pie',
};

http.Response recipeDetail(String externalId) => http.Response(
  jsonEncode({
    'external_id': externalId,
    'title': _detailTitles[externalId] ?? 'Recipe $externalId',
    'ingredients': [
      {'canonical_name': 'beans', 'quantity': 200, 'unit': 'g'},
    ],
  }),
  200,
);

/// A backend whose session finishes with [result] on its first poll and records every request.
http.Client proposalBackend({
  required Map<String, dynamic> result,
  void Function(http.Request request)? capture,
  Future<http.Response> Function()? holdPoll,
  Future<http.Response> Function()? holdDetail,
}) => MockClient((http.Request request) async {
  capture?.call(request);
  if (request.method == 'DELETE') return http.Response('', 204);
  if (request.method == 'POST') {
    return http.Response('{"session_id":"s1"}', 202);
  }
  if (request.url.path.startsWith('/meal-plan/sessions/')) {
    if (holdPoll != null) return holdPoll();
    return sessionDone(result);
  }
  if (holdDetail != null) return holdDetail();
  return recipeDetail(request.url.pathSegments.last);
});

GenerateProposalPhase refPhase(AppTestHarness h) =>
    h.container.read(generateWeekControllerProvider).phase;

void main() {
  final DateTime now = DateTime.now();
  final DateTime week = startOfWeek(now);

  Future<int> planMeal(
    AppTestHarness h,
    String externalId,
    String title, {
    int servings = 2,
  }) async {
    final int recipeId = await h.container
        .read(recipesRepositoryProvider)
        .save(
          userId: h.userId,
          externalId: externalId,
          title: title,
          ingredients: const [],
        );
    return h.container
        .read(planRepositoryProvider)
        .addEntry(
          userId: h.userId,
          recipeId: recipeId,
          recipeTitle: title,
          servings: servings,
          plannedDate: week,
        );
  }

  Future<void> openProposal(WidgetTester tester, AppTestHarness h) async {
    await h.pumpAt(tester, AppRoutes.plan.path);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
    await tester.pumpAndSettle();
  }

  Map<String, dynamic> sampleResult({bool degraded = false}) =>
      <String, dynamic>{
        'suggestions': <Map<String, dynamic>>[
          suggestion(
            'rec_a',
            title: 'Chicken katsu curry',
            reason: 'Uses up your coriander before it goes off.',
            reasonKind: 'urgent_item',
            alternative: alternative('rec_a_alt', 'Chicken & cashew stir-fry'),
          ),
          suggestion(
            'rec_b',
            title: 'Black bean tacos',
            reason: 'A quick meat-free night.',
            reasonKind: 'balance',
            alternative: alternative('rec_b_alt', 'Chickpea & spinach dal'),
          ),
        ],
        'week_summary': 'Four quick dinners: one fish, one meat-free.',
        'planned_alternatives': <Map<String, dynamic>>[],
        'degraded': degraded,
      };

  gleanWidgetTest(
    'the proposal shows the summary, one card per meal, the reason and the '
    'attribute placeholders',
    (tester) async {
      final h = AppTestHarness(
        httpClient: proposalBackend(result: sampleResult()),
      );
      addTearDown(h.dispose);

      await openProposal(tester, h);

      expect(find.text('This week'), findsOneWidget);
      expect(
        find.text('Four quick dinners: one fish, one meat-free.'),
        findsOneWidget,
      );
      expect(find.text('Chicken katsu curry'), findsOneWidget);
      expect(
        find.text('Uses up your coriander before it goes off.'),
        findsOneWidget,
      );
      expect(find.text('Black bean tacos'), findsOneWidget);
      expect(find.byType(ProposalAttributePlaceholders), findsNWidgets(2));
      expect(find.byType(ProposalMealCard), findsNWidgets(2));
      expect(find.text('Add 2 dinners to plan'), findsOneWidget);
      expect(
        find.textContaining('fish ·'),
        findsNothing,
        reason: 'no attribute values are invented before V5',
      );
      expect(
        find.descendant(
          of: find.byType(ProposalAttributePlaceholders).first,
          matching: find.byType(Container),
        ),
        findsNWidgets(3),
        reason: 'three empty chips, not fake attribute values',
      );
    },
  );

  gleanWidgetTest('Swap is local, instant and reversible, and saves nothing', (
    tester,
  ) async {
    final h = AppTestHarness(
      httpClient: proposalBackend(result: sampleResult()),
    );
    addTearDown(h.dispose);

    await openProposal(tester, h);
    await tester.tap(
      find.descendant(
        of: find.byKey(const ValueKey<String>('suggestion-0')),
        matching: find.text('Swap'),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Alternative: Chicken & cashew stir-fry'), findsOneWidget);

    await tester.tap(find.text('Use alternative'));
    await tester.pumpAndSettle();
    expect(find.text('Chicken & cashew stir-fry'), findsOneWidget);
    expect(find.text('Chicken katsu curry'), findsNothing);
    expect(find.text('Swap back'), findsOneWidget);
    expect(
      await tester.runAsync(
        () => h.container
            .read(planRepositoryProvider)
            .getWeek(userId: h.userId, weekStart: week),
      ),
      isEmpty,
      reason: 'a swap is a choice, not a write',
    );

    await tester.tap(
      find.descendant(
        of: find.byKey(const ValueKey<String>('suggestion-0')),
        matching: find.text('Swap back'),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Chicken katsu curry'), findsOneWidget);
    expect(find.text('Chicken & cashew stir-fry'), findsNothing);
  });

  gleanWidgetTest('Add to plan saves the swapped meal, and only then', (
    tester,
  ) async {
    final h = AppTestHarness(
      httpClient: proposalBackend(result: sampleResult()),
    );
    addTearDown(h.dispose);

    await openProposal(tester, h);
    await tester.tap(
      find.descendant(
        of: find.byKey(const ValueKey<String>('suggestion-0')),
        matching: find.text('Swap'),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Use alternative'));
    await tester.pumpAndSettle();

    expect(
      await tester.runAsync(
        () => h.container
            .read(planRepositoryProvider)
            .getWeek(userId: h.userId, weekStart: week),
      ),
      isEmpty,
    );

    await tester.tap(find.text('Add 2 dinners to plan'));
    await tester.pumpAndSettle();

    final entries = await tester.runAsync(
      () => h.container
          .read(planRepositoryProvider)
          .getWeek(userId: h.userId, weekStart: week),
    );
    expect(entries, hasLength(2));
    expect(
      entries!.map((entry) => entry.recipeTitle),
      containsAll(<String>['Chicken & cashew stir-fry', 'Black bean tacos']),
    );
    expect(
      entries.map((entry) => entry.recipeTitle),
      isNot(contains('Chicken katsu curry')),
    );
  });

  gleanWidgetTest(
    'a planned meal is greyed, tagged and swappable, and Add updates its entry',
    (tester) async {
      final h = AppTestHarness(
        httpClient: proposalBackend(
          result: <String, dynamic>{
            'suggestions': <Map<String, dynamic>>[
              suggestion(
                'rec_new',
                title: 'Pork & ginger noodles',
                reason: 'The week needs a noodle night.',
              ),
            ],
            'week_summary': 'One new dinner.',
            'planned_alternatives': <Map<String, dynamic>>[
              {
                'external_id': 'rec_planned',
                'alternative': alternative('rec_planned_alt', 'Fish pie'),
              },
            ],
          },
        ),
      );
      addTearDown(h.dispose);
      final int entryId = await planMeal(h, 'rec_planned', 'Leftover lasagne');

      await openProposal(tester, h);

      expect(find.text('Leftover lasagne'), findsOneWidget);
      expect(find.text('already planned'), findsOneWidget);
      expect(find.text('Add 1 dinner to plan'), findsOneWidget);
      final Finder plannedCard = find.byKey(
        ValueKey<String>('planned-$entryId'),
      );
      expect(
        find.descendant(of: plannedCard, matching: find.text('Swap')),
        findsOneWidget,
      );

      await tester.tap(
        find.descendant(of: plannedCard, matching: find.text('Swap')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Use alternative'));
      await tester.pumpAndSettle();
      expect(find.text('Fish pie'), findsOneWidget);

      await tester.tap(find.text('Add 1 dinner to plan'));
      await tester.pumpAndSettle();

      final entries = await tester.runAsync(
        () => h.container
            .read(planRepositoryProvider)
            .getWeek(userId: h.userId, weekStart: week),
      );
      expect(
        entries,
        hasLength(2),
        reason: 'the planned entry is updated, not replaced by a second',
      );
      final swapped = entries!.singleWhere((entry) => entry.id == entryId);
      expect(swapped.recipeTitle, 'Fish pie');
      expect(swapped.externalIdSnapshot, 'rec_planned_alt');
      final shopping = await tester.runAsync(
        () => h.container
            .read(shoppingRepositoryProvider)
            .watchAll(h.userId)
            .first,
      );
      expect(
        shopping!.any((row) => row.name == 'beans'),
        isTrue,
        reason: 'shopping gaps come from the swapped recipe',
      );
    },
  );

  gleanWidgetTest(
    'a partial week lists the planned meals greyed at the top and Add counts '
    'only the new meals',
    (tester) async {
      final h = AppTestHarness(
        httpClient: proposalBackend(
          result: <String, dynamic>{
            'suggestions': <Map<String, dynamic>>[
              suggestion('rec_a', title: 'New one', reason: 'Fits.'),
              suggestion('rec_b', title: 'New two', reason: 'Also fits.'),
            ],
            'week_summary': 'Two more dinners.',
            'planned_alternatives': <Map<String, dynamic>>[],
          },
        ),
      );
      addTearDown(h.dispose);
      final int entryId = await planMeal(h, 'rec_planned', 'Already there');

      await openProposal(tester, h);

      expect(find.text('already planned'), findsOneWidget);
      expect(find.text('Add 2 dinners to plan'), findsOneWidget);
      expect(
        tester.getTopLeft(find.byKey(ValueKey<String>('planned-$entryId'))).dy,
        lessThan(
          tester
              .getTopLeft(find.byKey(const ValueKey<String>('suggestion-0')))
              .dy,
        ),
      );

      await tester.tap(find.text('Add 2 dinners to plan'));
      await tester.pumpAndSettle();

      final entries = await tester.runAsync(
        () => h.container
            .read(planRepositoryProvider)
            .getWeek(userId: h.userId, weekStart: week),
      );
      expect(entries, hasLength(3));
      expect(
        entries!.singleWhere((entry) => entry.id == entryId).recipeTitle,
        'Already there',
        reason: 'a planned meal is never replaced automatically',
      );
    },
  );

  gleanWidgetTest('no meals is its own state with the approved copy', (
    tester,
  ) async {
    final h = AppTestHarness(
      httpClient: proposalBackend(
        result: <String, dynamic>{
          'suggestions': <Map<String, dynamic>>[],
          'week_summary': 'Nothing to plan this week.',
        },
      ),
    );
    addTearDown(h.dispose);

    await openProposal(tester, h);

    expect(find.text('No meals to suggest'), findsOneWidget);
    expect(
      find.text('No recipes fit your diet and time limit.'),
      findsOneWidget,
    );
    expect(find.text('Open Settings'), findsOneWidget);
    expect(find.textContaining('Add '), findsNothing);
    expect(find.text('Close'), findsOneWidget);
  });

  gleanWidgetTest('a degraded proposal looks exactly like any other', (
    tester,
  ) async {
    final h = AppTestHarness(
      httpClient: proposalBackend(result: sampleResult(degraded: true)),
    );
    addTearDown(h.dispose);

    await openProposal(tester, h);

    // The same content a normal proposal shows: summary, both cards, their reasons, the swap affordance and
    // the attribute placeholders. Nothing announces the fallback and nothing is hidden because of it.
    expect(find.text('This week'), findsOneWidget);
    expect(
      find.text('Four quick dinners: one fish, one meat-free.'),
      findsOneWidget,
    );
    expect(find.byType(ProposalMealCard), findsNWidgets(2));
    expect(find.text('Chicken katsu curry'), findsOneWidget);
    expect(
      find.text('Uses up your coriander before it goes off.'),
      findsOneWidget,
    );
    expect(find.text('Black bean tacos'), findsOneWidget);
    expect(find.text('Swap'), findsNWidgets(2));
    expect(find.byType(ProposalAttributePlaceholders), findsNWidgets(2));
    expect(find.textContaining('degraded'), findsNothing);
    expect(find.text('Add 2 dinners to plan'), findsOneWidget);
  });

  gleanWidgetTest('Cancel DELETEs the session, closes and saves nothing', (
    tester,
  ) async {
    final requests = <http.Request>[];
    final pending = Completer<http.Response>();
    final h = AppTestHarness(
      httpClient: proposalBackend(
        result: sampleResult(),
        capture: requests.add,
        holdPoll: () => pending.future,
      ),
    );
    addTearDown(h.dispose);

    await h.pumpAt(tester, AppRoutes.plan.path);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
    await pumpUntil(
      tester,
      () =>
          find.text('Cancel').evaluate().isNotEmpty &&
          requests.any(
            (request) =>
                request.method == 'GET' &&
                request.url.path.startsWith('/meal-plan/sessions/'),
          ),
      description: 'the working state with a session to cancel',
    );
    // Let the push transition finish: the tap must land on the settled bottom bar.
    await tester.pump(const Duration(milliseconds: 500));

    expect(
      h.container.read(generateWeekControllerProvider).sessionId,
      's1',
      reason: 'the session exists before Cancel can DELETE it',
    );
    await tester.tap(find.text('Cancel'));
    await tester.pump();
    pending.complete(sessionDone(sampleResult()));
    await tester.pumpAndSettle();

    final deletes = requests.where((request) => request.method == 'DELETE');
    expect(deletes, hasLength(1));
    expect(deletes.single.url.path, '/meal-plan/sessions/s1');
    expect(find.widgetWithText(FilledButton, 'Generate'), findsOneWidget);
    expect(
      await tester.runAsync(
        () => h.container
            .read(planRepositoryProvider)
            .getWeek(userId: h.userId, weekStart: week),
      ),
      isEmpty,
    );
  });

  gleanWidgetTest('Back discards the proposal and cancels the session', (
    tester,
  ) async {
    final requests = <http.Request>[];
    final h = AppTestHarness(
      httpClient: proposalBackend(
        result: sampleResult(),
        capture: requests.add,
      ),
    );
    addTearDown(h.dispose);

    await openProposal(tester, h);
    expect(find.text('Chicken katsu curry'), findsOneWidget);

    await tester.tap(find.byTooltip('Back'));
    await tester.pumpAndSettle();

    expect(
      requests.where((request) => request.method == 'DELETE'),
      hasLength(1),
    );
    expect(find.widgetWithText(FilledButton, 'Generate'), findsOneWidget);
    expect(
      await tester.runAsync(
        () => h.container
            .read(planRepositoryProvider)
            .getWeek(userId: h.userId, weekStart: week),
      ),
      isEmpty,
    );
  });

  gleanWidgetTest(
    'a double-tap on Add saves once and shows exactly one Undo snackbar',
    (tester) async {
      final Completer<http.Response> heldDetail = Completer<http.Response>();
      var detailStarted = false;
      final h = AppTestHarness(
        httpClient: proposalBackend(
          result: <String, dynamic>{
            'suggestions': <Map<String, dynamic>>[
              suggestion('rec_a', title: 'Dinner A', reason: 'Fits.'),
            ],
            'week_summary': 'One dinner.',
          },
          holdDetail: () {
            detailStarted = true;
            return heldDetail.future;
          },
        ),
      );
      addTearDown(h.dispose);

      await openProposal(tester, h);
      // Both taps land before any frame can rebuild the disabled button.
      await tester.tap(find.text('Add 1 dinner to plan'));
      await tester.tap(find.text('Add 1 dinner to plan'));
      await pumpUntil(
        tester,
        () => detailStarted,
        description: 'the first save resolving a detail',
      );
      await tester.pump(const Duration(milliseconds: 300));
      expect(
        refPhase(h),
        GenerateProposalPhase.proposal,
        reason: 'the refused second request must not pop the review',
      );

      heldDetail.complete(recipeDetail('rec_a'));
      await tester.pumpAndSettle();

      expect(
        await tester.runAsync(
          () => h.container
              .read(planRepositoryProvider)
              .getWeek(userId: h.userId, weekStart: week),
        ),
        hasLength(1),
        reason: 'one save ran, not two',
      );
      expect(find.text('Undo'), findsOneWidget);
      expect(
        find.text('Week updated.'),
        findsNothing,
        reason: 'the refused request reports no save',
      );
    },
  );

  gleanWidgetTest(
    'Back while Add resolves details aborts the save, with no second pop',
    (tester) async {
      final Completer<http.Response> heldDetail = Completer<http.Response>();
      var detailStarted = false;
      final h = AppTestHarness(
        httpClient: proposalBackend(
          result: <String, dynamic>{
            'suggestions': <Map<String, dynamic>>[
              suggestion('rec_a', title: 'Dinner A', reason: 'Fits.'),
            ],
            'week_summary': 'One dinner.',
          },
          holdDetail: () {
            detailStarted = true;
            return heldDetail.future;
          },
        ),
      );
      addTearDown(h.dispose);

      await openProposal(tester, h);
      await tester.tap(find.text('Add 1 dinner to plan'));
      await pumpUntil(
        tester,
        () => detailStarted,
        description: 'the save resolving a recipe detail',
      );
      await tester.tap(find.byTooltip('Back'));
      await tester.pump(const Duration(milliseconds: 500));
      expect(
        find.widgetWithText(FilledButton, 'Generate'),
        findsOneWidget,
        reason: 'Back closes the review while the save is still resolving',
      );

      heldDetail.complete(recipeDetail('rec_a'));
      await tester.pumpAndSettle();

      expect(
        tester.takeException(),
        isNull,
        reason: 'a stale save completion must not pop a second time',
      );
      expect(
        await tester.runAsync(
          () => h.container
              .read(planRepositoryProvider)
              .getWeek(userId: h.userId, weekStart: week),
        ),
        isEmpty,
        reason: 'the discarded review never reaches its transaction',
      );
    },
  );

  for (final double scale in <double>[1.3, 2.0]) {
    gleanWidgetTest(
      'the review fits a 320 px screen at ${scale}x text, proposal and swap',
      (tester) async {
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
        tester.view.physicalSize = const Size(320, 844);
        tester.view.devicePixelRatio = 1;
        tester.platformDispatcher.textScaleFactorTestValue = scale;

        final h = AppTestHarness(
          httpClient: proposalBackend(result: sampleResult()),
        );
        addTearDown(h.dispose);

        await openProposal(tester, h);
        expect(
          tester.takeException(),
          isNull,
          reason: 'the bottom action bar must wrap, not overflow',
        );
        expect(find.text('Add 2 dinners to plan'), findsOneWidget);

        await tester.tap(
          find.descendant(
            of: find.byKey(const ValueKey<String>('suggestion-0')),
            matching: find.text('Swap'),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('Use alternative'), findsOneWidget);
        expect(
          tester.takeException(),
          isNull,
          reason: 'the swap panel action must wrap inside the card too',
        );
      },
    );
  }

  gleanWidgetTest(
    'Undo restores a swapped planned meal and removes the week Add inserted',
    (tester) async {
      final h = AppTestHarness(
        httpClient: proposalBackend(
          result: <String, dynamic>{
            'suggestions': <Map<String, dynamic>>[
              suggestion('rec_new', title: 'New dinner', reason: 'Fits.'),
            ],
            'week_summary': 'One new dinner.',
            'planned_alternatives': <Map<String, dynamic>>[
              {
                'external_id': 'rec_planned',
                'alternative': alternative('rec_planned_alt', 'Fish pie'),
              },
            ],
          },
        ),
      );
      addTearDown(h.dispose);

      final recipes = h.container.read(recipesRepositoryProvider);
      final plan = h.container.read(planRepositoryProvider);
      final shopping = h.container.read(shoppingRepositoryProvider);
      final int plannedRecipeId = await recipes.save(
        userId: h.userId,
        externalId: 'rec_planned',
        title: 'Leftover lasagne',
        ingredients: const <SaveRecipeIngredient>[
          SaveRecipeIngredient(canonicalName: 'peas', quantity: 100, unit: 'g'),
        ],
      );
      final int entryId = await plan.addEntry(
        userId: h.userId,
        recipeId: plannedRecipeId,
        recipeTitle: 'Leftover lasagne',
        servings: 2,
        plannedDate: week,
      );
      await shopping.addGapsForRecipe(
        userId: h.userId,
        recipeId: plannedRecipeId,
        servings: 2,
        sourceMealPlanEntryId: entryId,
      );
      // A stale rating on a planned row, which the swap drops and Undo must put back.
      await h.db.customStatement(
        'INSERT INTO meal_ratings '
        '(user_id, meal_plan_entry_id, rating, note, created_at) '
        'VALUES (?, ?, ?, ?, ?)',
        <Object?>[
          h.userId,
          entryId,
          'down',
          'too sweet',
          DateTime.utc(2026, 10, 6).toIso8601String(),
        ],
      );

      await openProposal(tester, h);
      await tester.tap(
        find.descendant(
          of: find.byKey(ValueKey<String>('planned-$entryId')),
          matching: find.text('Swap'),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Use alternative'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Add 1 dinner to plan'));
      await tester.pumpAndSettle();

      expect(find.text('Undo'), findsOneWidget, reason: 'Add offers Undo');
      await tester.tap(find.text('Undo'));
      await tester.pumpAndSettle();

      final entries = await tester.runAsync(
        () => plan.getWeek(userId: h.userId, weekStart: week),
      );
      expect(entries, hasLength(1), reason: 'the inserted dinner is gone');
      final restored = entries!.single;
      expect(restored.recipeId, plannedRecipeId);
      expect(restored.recipeTitle, 'Leftover lasagne');
      expect(restored.externalIdSnapshot, 'rec_planned');
      expect(restored.rating, MealThumb.down);
      expect(restored.note, 'too sweet');

      final rows = await tester.runAsync(
        () => shopping.watchAll(h.userId).first,
      );
      expect(
        rows!.map((row) => row.name),
        contains('peas'),
        reason: 'the planned meal gets its own shopping demand back',
      );
      expect(
        rows.map((row) => row.name),
        isNot(contains('beans')),
        reason: 'the swapped alternative\'s demand is gone',
      );
    },
  );

  gleanWidgetTest(
    'an older backend result shows no summary and no swap, and still adds',
    (tester) async {
      final h = AppTestHarness(
        httpClient: proposalBackend(
          result: <String, dynamic>{
            'suggestions': <Map<String, dynamic>>[
              suggestion('rec_a', title: 'Old soup', reason: 'Warms you up.'),
            ],
          },
        ),
      );
      addTearDown(h.dispose);

      await openProposal(tester, h);
      expect(find.text('This week'), findsNothing);
      expect(find.text('Swap'), findsNothing);
      expect(find.text('Old soup'), findsOneWidget);

      await tester.tap(find.text('Add 1 dinner to plan'));
      await tester.pumpAndSettle();
      expect(
        await tester.runAsync(
          () => h.container
              .read(planRepositoryProvider)
              .getWeek(userId: h.userId, weekStart: week),
        ),
        hasLength(1),
      );
    },
  );
}
