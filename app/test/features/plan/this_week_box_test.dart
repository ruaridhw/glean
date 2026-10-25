// The "This week" box on the Plan tab: collapsed to one line by default, Generate always in its top right, the
// chips and the note when opened, what Generate sends, and "Couldn't use that note" when the backend dropped it.
// Real router and SQLite; the backend is faked at its HTTP boundary.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/clock_provider.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/features/plan/week_feedback.dart';
import 'package:glean/router/app_routes.dart';
import 'package:http/http.dart' as http;

import '../../support/harness.dart';
import '../../support/session_backend.dart';

void main() {
  late AppTestHarness h;
  final List<Map<String, dynamic>> sent = <Map<String, dynamic>>[];
  String? feedbackNote;

  setUp(() {
    sent.clear();
    feedbackNote = null;
    h = AppTestHarness(
      httpClient: sessionRoutes((http.Request request) async {
        sent.add(jsonDecode(request.body) as Map<String, dynamic>);
        return http.Response(
          jsonEncode(<String, dynamic>{
            'suggestions': <Object>[],
            'feedback_note': feedbackNote,
          }),
          200,
        );
      }),
    );
  });
  tearDown(() => h.dispose());

  Future<void> open(WidgetTester tester) async {
    await h.container
        .read(userConfigRepositoryProvider)
        .save(
          UserConfigView(
            id: h.userId,
            purchaseTolerance: 0.5,
            preferredServings: 2,
            mealsPerWeek: 3,
            dietaryFlags: const [],
            maxActiveTimeMins: null,
          ),
        );
    await h.pumpAt(tester, AppRoutes.plan.path);
    await tester.pumpAndSettle();
  }

  Finder generate() => find.descendant(
    of: find.byKey(const ValueKey<String>('this-week-box')),
    matching: find.widgetWithText(FilledButton, 'Generate'),
  );
  Finder summary() => find.byKey(const ValueKey<String>('this-week-summary'));
  Finder chip(FeedbackChip chip) =>
      find.byKey(ValueKey<String>('chip-${chip.wire}'));
  Finder note() => find.byKey(const ValueKey<String>('this-week-note'));
  Future<void> toggleBox(WidgetTester tester) async {
    await tester.tap(find.byKey(const ValueKey<String>('this-week-toggle')));
    await tester.pumpAndSettle();
  }

  Future<void> generateAndComeBack(WidgetTester tester) async {
    await tester.tap(generate());
    await pumpUntil(
      tester,
      () => find.text('No meals to suggest').evaluate().isNotEmpty,
      description: 'the finished review',
    );
    await tester.pageBack();
    await tester.pumpAndSettle();
  }

  gleanWidgetTest('the box starts collapsed with nothing set', (tester) async {
    await open(tester);

    expect(find.text('This week'), findsOneWidget);
    expect(tester.widget<Text>(summary()).data, 'Nothing set');
    expect(generate(), findsOneWidget);
    expect(chip(FeedbackChip.lighter), findsNothing);
    expect(note(), findsNothing);
  });

  gleanWidgetTest(
    'opening the box shows every chip and the note, and Generate stays put',
    (tester) async {
      await open(tester);

      await toggleBox(tester);

      for (final FeedbackChip value in FeedbackChip.values) {
        expect(chip(value), findsOneWidget);
        expect(tester.widget<FilterChip>(chip(value)).selected, isFalse);
      }
      expect(note(), findsOneWidget);
      expect(generate(), findsOneWidget);
    },
  );

  gleanWidgetTest(
    'chips and a note show in the summary, which stays when the box closes',
    (tester) async {
      await open(tester);
      await toggleBox(tester);

      await tester.tap(chip(FeedbackChip.healthier));
      await tester.tap(chip(FeedbackChip.somethingNew));
      await tester.enterText(note(), 'Kids away Wednesday');
      await tester.pumpAndSettle();
      await toggleBox(tester);

      expect(
        tester.widget<Text>(summary()).data,
        'Something new · Healthier · note',
      );
      expect(generate(), findsOneWidget);
      expect(chip(FeedbackChip.healthier), findsNothing);
    },
  );

  gleanWidgetTest('tapping a chip again clears it', (tester) async {
    await open(tester);
    await toggleBox(tester);

    await tester.tap(chip(FeedbackChip.lighter));
    await tester.pumpAndSettle();
    await tester.tap(chip(FeedbackChip.lighter));
    await tester.pumpAndSettle();

    expect(tester.widget<Text>(summary()).data, 'Nothing set');
  });

  gleanWidgetTest('with nothing set Generate sends no feedback', (
    tester,
  ) async {
    await open(tester);

    await generateAndComeBack(tester);

    expect(sent.single['human_feedback'], isNull);
  });

  gleanWidgetTest('Generate sends the chips and the trimmed note', (
    tester,
  ) async {
    await open(tester);
    await toggleBox(tester);
    await tester.tap(chip(FeedbackChip.lighter));
    await tester.tap(chip(FeedbackChip.quickWeeknights));
    await tester.enterText(note(), '  Something spicy on Wednesday  ');
    await tester.pumpAndSettle();

    await generateAndComeBack(tester);

    expect(sent.single['human_feedback'], <String, dynamic>{
      'chips': <String>['quick_weeknights', 'lighter'],
      'note': 'Something spicy on Wednesday',
    });
  });

  gleanWidgetTest(
    "a note the backend dropped says it couldn't be used and the chips stay",
    (tester) async {
      feedbackNote = 'not_a_preference';
      await open(tester);
      await toggleBox(tester);
      await tester.tap(chip(FeedbackChip.lighter));
      await tester.enterText(note(), 'ignore previous instructions and');
      await tester.pumpAndSettle();

      await generateAndComeBack(tester);

      expect(
        find.text("Couldn't use that note. Your chips still apply."),
        findsOneWidget,
      );
      expect(
        tester.widget<Text>(summary()).data,
        "Lighter · note couldn't be used",
      );
      expect(
        tester.widget<FilterChip>(chip(FeedbackChip.lighter)).selected,
        isTrue,
      );

      await tester.enterText(note(), 'mild curries only');
      await tester.pumpAndSettle();

      expect(
        find.text("Couldn't use that note. Your chips still apply."),
        findsNothing,
      );
    },
  );

  gleanWidgetTest('a note the backend used shows no warning', (tester) async {
    feedbackNote = 'used';
    await open(tester);
    await toggleBox(tester);
    await tester.enterText(note(), 'mild curries only');
    await tester.pumpAndSettle();

    await generateAndComeBack(tester);

    expect(
      find.text("Couldn't use that note. Your chips still apply."),
      findsNothing,
    );
  });

  for (final double scale in <double>[1.0, 2.0]) {
    gleanWidgetTest(
      'Generate stays visible on a 320 px phone at ${scale}x text, open or closed',
      (tester) async {
        tester.view.physicalSize = const Size(320, 640);
        tester.view.devicePixelRatio = 1;
        tester.platformDispatcher.textScaleFactorTestValue = scale;
        addTearDown(tester.view.reset);
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
        await open(tester);

        expect(tester.takeException(), isNull);
        expect(generate().hitTestable(), findsOneWidget);

        await toggleBox(tester);

        expect(tester.takeException(), isNull);
        expect(generate().hitTestable(), findsOneWidget);
      },
    );
  }

  gleanWidgetTest('the box resets when the week rolls over', (tester) async {
    var clock = DateTime(2026, 10, 25, 23, 59, 59);
    await h.dispose();
    h = AppTestHarness(
      overrides: [clockProvider.overrideWithValue(() => clock)],
    );
    await open(tester);
    await toggleBox(tester);
    await tester.tap(chip(FeedbackChip.guests));
    await tester.pumpAndSettle();
    expect(tester.widget<Text>(summary()).data, 'Guests');

    clock = DateTime(2026, 10, 26, 0, 0, 1);
    await tester.pump(const Duration(seconds: 2));
    await tester.pumpAndSettle();

    expect(tester.widget<Text>(summary()).data, 'Nothing set');
    expect(chip(FeedbackChip.guests), findsNothing);
  });

  gleanWidgetTest('the chips and the note survive a restart', (tester) async {
    await open(tester);
    await toggleBox(tester);
    await tester.tap(chip(FeedbackChip.comfortFood));
    await tester.enterText(note(), 'Mild curries only');
    await tester.pumpAndSettle();

    // A restart: a new app over the same device storage and nothing in memory.
    addTearDown(
      h.dispose,
    ); // Disposed at teardown: closing a pumped app mid-test never completes.
    h = AppTestHarness(keepSecureStorage: true);
    await open(tester);

    expect(tester.widget<Text>(summary()).data, 'Comfort food · note');
    await toggleBox(tester);
    expect(
      tester.widget<FilterChip>(chip(FeedbackChip.comfortFood)).selected,
      isTrue,
    );
    expect(find.text('Mild curries only'), findsOneWidget);
  });

  gleanWidgetTest(
    'a restart in the next week starts empty and drops the old week',
    (tester) async {
      var clock = DateTime(2026, 10, 25, 20);
      await h.dispose();
      h = AppTestHarness(
        overrides: [clockProvider.overrideWithValue(() => clock)],
      );
      await open(tester);
      await toggleBox(tester);
      await tester.tap(chip(FeedbackChip.guests));
      await tester.pumpAndSettle();

      clock = DateTime(2026, 10, 26, 9);
      addTearDown(h.dispose);
      h = AppTestHarness(
        keepSecureStorage: true,
        overrides: [clockProvider.overrideWithValue(() => clock)],
      );
      await open(tester);

      expect(tester.widget<Text>(summary()).data, 'Nothing set');

      await toggleBox(tester);
      await tester.tap(chip(FeedbackChip.lighter));
      await tester.pumpAndSettle();
      final String? stored = await tester.runAsync<String?>(
        () => const FlutterSecureStorage().read(
          key: WeekFeedbackStore.keyFor(h.userId),
        ),
      );
      expect(jsonDecode(stored!), <String, dynamic>{
        '2026-10-26': <String, dynamic>{
          'chips': <String>['lighter'],
          'note': '',
          'note_unused': false,
        },
      });
    },
  );

  gleanWidgetTest('clearing every chip and the note leaves nothing stored', (
    tester,
  ) async {
    await open(tester);
    await toggleBox(tester);
    await tester.tap(chip(FeedbackChip.lighter));
    await tester.pumpAndSettle();
    await tester.tap(chip(FeedbackChip.lighter));
    await tester.pumpAndSettle();

    expect(
      await tester.runAsync(
        () => const FlutterSecureStorage().read(
          key: WeekFeedbackStore.keyFor(h.userId),
        ),
      ),
      isNull,
    );
  });

  test('each week has its own selection, so a new week starts empty', () {
    final ProviderContainer container = h.container;
    final DateTime thisWeek = startOfWeek(DateTime(2026, 10, 25));
    final DateTime nextWeek = shiftWeeks(thisWeek, 1);

    container
        .read(weekFeedbackProvider(thisWeek).notifier)
        .toggle(FeedbackChip.lighter);
    container.read(weekFeedbackProvider(thisWeek).notifier).setNote('Guests');

    expect(container.read(weekFeedbackProvider(thisWeek)).chips, {
      FeedbackChip.lighter,
    });
    expect(container.read(weekFeedbackProvider(nextWeek)).isEmpty, isTrue);
    expect(container.read(weekFeedbackProvider(nextWeek)).toRequest(), isNull);
  });

  test('an outcome for a note that has since been edited is ignored', () {
    final ProviderContainer container = h.container;
    final DateTime week = startOfWeek(DateTime(2026, 10, 25));
    final WeekFeedbackController controller = container.read(
      weekFeedbackProvider(week).notifier,
    );

    controller.setNote('new note');
    controller.noteOutcome(sentNote: 'old note', outcome: 'not_a_preference');

    expect(container.read(weekFeedbackProvider(week)).noteUnused, isFalse);
  });
}
