// The "This week" box on the Plan tab: collapsed to one line by default, Generate always in its top right, the
// chips and the note when opened, what Generate sends, and "Couldn't use that note" when the backend dropped it.
// Real router and SQLite; the backend is faked at its HTTP boundary.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/auth_controller.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/clock_provider.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/features/plan/presentation.dart';
import 'package:glean/features/plan/week_feedback.dart';
import 'package:glean/router/app_routes.dart';
import 'package:http/http.dart' as http;

import '../../support/harness.dart';
import '../../support/session_backend.dart';

void main() {
  late AppTestHarness h;
  final List<Map<String, dynamic>> sent = <Map<String, dynamic>>[];
  String? feedbackNote;

  // The backend at its HTTP boundary: records what Generate sent, and answers with [feedbackNote].
  http.Client backend() => sessionRoutes((http.Request request) async {
    sent.add(jsonDecode(request.body) as Map<String, dynamic>);
    return http.Response(
      jsonEncode(<String, dynamic>{
        'suggestions': <Object>[],
        'feedback_note': feedbackNote,
      }),
      200,
    );
  });

  setUp(() {
    sent.clear();
    feedbackNote = null;
    h = AppTestHarness(httpClient: backend());
  });
  tearDown(() => h.dispose());

  Future<void> open(WidgetTester tester, {int meals = 3}) async {
    await h.container
        .read(userConfigRepositoryProvider)
        .save(
          UserConfigView(
            id: h.userId,
            purchaseTolerance: 0.5,
            preferredServings: 2,
            mealsPerWeek: meals,
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

  gleanWidgetTest(
    'a selected chip is dark, checked and announced as selected',
    (tester) async {
      await open(tester);
      await toggleBox(tester);

      await tester.tap(chip(FeedbackChip.lighter));
      await tester.pumpAndSettle();

      final ColorScheme scheme = Theme.of(
        tester.element(chip(FeedbackChip.lighter)),
      ).colorScheme;
      final FilterChip on = tester.widget<FilterChip>(
        chip(FeedbackChip.lighter),
      );
      expect(on.selected, isTrue);
      expect(on.selectedColor, scheme.inverseSurface);
      expect(on.showCheckmark, isTrue);
      expect(
        tester.getSemantics(chip(FeedbackChip.lighter)),
        matchesSemantics(
          isSelected: true,
          hasSelectedState: true,
          isButton: true,
          hasEnabledState: true,
          isEnabled: true,
          isFocusable: true,
          hasTapAction: true,
          hasFocusAction: true,
          label: 'Lighter',
        ),
      );
      expect(
        tester.widget<FilterChip>(chip(FeedbackChip.guests)).selected,
        isFalse,
      );
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

  gleanWidgetTest('with no profile Generate sends none', (tester) async {
    await open(tester);

    await generateAndComeBack(tester);

    expect(sent.single.containsKey('profile'), isTrue);
    expect(sent.single['profile'], isNull);
  });

  gleanWidgetTest(
    'a profile that cannot be read is sent as none and Generate still goes',
    (tester) async {
      await open(tester);
      // The table is gone: every read of the profile throws, as a corrupt or half-migrated database would.
      await h.db.customStatement('DROP TABLE household_profiles');

      await generateAndComeBack(tester);

      expect(sent.single['profile'], isNull);
    },
  );

  gleanWidgetTest('Generate sends the stored profile, bounded for the wire', (
    tester,
  ) async {
    await h.container
        .read(householdProfileRepositoryProvider)
        .save(
          userId: h.userId,
          profile: HouseholdProfile(
            dislikedIngredients: <String>['mushrooms', 'x' * 80],
            cuisinesLiked: const <String>['Italian'],
            proteinTargets: const <ProteinTarget>[
              ProteinTarget(protein: 'fish', minPerWeek: 1),
            ],
            spiceTolerance: SpiceTolerance.mild,
            habits: 'Quick weeknights',
          ),
        );
    await open(tester);

    await generateAndComeBack(tester);

    final Map<String, dynamic> profile =
        sent.single['profile'] as Map<String, dynamic>;
    expect(profile['disliked_ingredients'], <String>['mushrooms', 'x' * 60]);
    expect(profile['cuisines_liked'], <String>['Italian']);
    expect(profile['protein_targets'], <Map<String, dynamic>>[
      <String, dynamic>{
        'protein': 'fish',
        'min_per_week': 1,
        'max_per_week': null,
      },
    ]);
    expect(profile['spice_tolerance'], 'mild');
    expect(profile['habits'], 'Quick weeknights');
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
        "Note couldn't be used · Lighter",
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
      'Generate stays pinned on a 320 px phone at ${scale}x text, open or closed, however far the plan scrolls',
      (tester) async {
        tester.view.physicalSize = const Size(320, 640);
        tester.view.devicePixelRatio = 1;
        tester.platformDispatcher.textScaleFactorTestValue = scale;
        addTearDown(tester.view.reset);
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
        // A full week, so the plan is longer than the screen and really scrolls.
        await open(tester, meals: 7);
        Future<void> scrollToTheEnd() async {
          await tester.drag(find.byType(ListView), const Offset(0, -3000));
          await tester.pumpAndSettle();
        }

        expect(tester.takeException(), isNull);
        expect(generate().hitTestable(), findsOneWidget);
        await scrollToTheEnd();
        expect(find.byTooltip('Next week').hitTestable(), findsNothing);
        expect(generate().hitTestable(), findsOneWidget);

        await tester.drag(find.byType(ListView), const Offset(0, 3000));
        await tester.pumpAndSettle();
        await toggleBox(tester);

        expect(tester.takeException(), isNull);
        expect(generate().hitTestable(), findsOneWidget);
        await scrollToTheEnd();
        expect(chip(FeedbackChip.lighter).hitTestable(), findsNothing);
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

  gleanWidgetTest(
    'a note is bounded by code points, so Generate never sends more than the backend takes',
    (tester) async {
      await open(tester);
      await toggleBox(tester);
      // 150 letters and 25 "thumbs up, medium skin tone": 175 visible characters, exactly 200 code points.
      final String full = '${'a' * 150}${'👍🏽' * 25}';
      await tester.enterText(note(), full);
      await tester.pumpAndSettle();

      // Five more emoji would be 180 visible characters, which maxLength would allow, but 210 code points.
      await tester.enterText(note(), '$full${'👍🏽' * 5}');
      await tester.pumpAndSettle();
      await generateAndComeBack(tester);

      final String sentNote =
          (sent.single['human_feedback'] as Map<String, dynamic>)['note']
              as String;
      expect(sentNote.runes.length, maxWeekNoteLength);
      expect(sentNote, full);
    },
  );

  gleanWidgetTest(
    'typing into the middle of a full note changes nothing and leaves the cursor where it was',
    (tester) async {
      await open(tester);
      await toggleBox(tester);
      final String full = 'a' * maxWeekNoteLength;
      await tester.enterText(note(), full);
      await tester.pumpAndSettle();
      final TextField field = tester.widget<TextField>(note());
      field.controller!.selection = const TextSelection.collapsed(offset: 100);
      await tester.pumpAndSettle();

      // One more character typed at the cursor, as the keyboard would send it.
      tester.testTextInput.updateEditingValue(
        TextEditingValue(
          text: '${'a' * 100}X${'a' * 100}',
          selection: const TextSelection.collapsed(offset: 101),
        ),
      );
      await tester.pumpAndSettle();

      expect(field.controller!.text, full);
      expect(
        field.controller!.selection,
        const TextSelection.collapsed(offset: 100),
      );
    },
  );

  gleanWidgetTest(
    'an over-long note saved by an older build is clipped when it loads',
    (tester) async {
      final DateTime week = startOfWeek(DateTime.now());
      String two(int value) => value.toString().padLeft(2, '0');
      final String key = '${week.year}-${two(week.month)}-${two(week.day)}';
      await h.dispose();
      FlutterSecureStorage.setMockInitialValues(<String, String>{
        WeekFeedbackStore.keyFor('test-user'): jsonEncode(<String, dynamic>{
          key: <String, dynamic>{
            'chips': <String>['lighter'],
            'note': '👍🏽' * 150,
            'note_unused': false,
          },
        }),
      });
      h = AppTestHarness(keepSecureStorage: true, httpClient: backend());
      await open(tester);

      await generateAndComeBack(tester);

      final String sentNote =
          (sent.single['human_feedback'] as Map<String, dynamic>)['note']
              as String;
      expect(sentNote, '👍🏽' * 100);
    },
  );

  gleanWidgetTest(
    'a past week is dropped when the box reads, before any edit',
    (tester) async {
      await h.dispose();
      FlutterSecureStorage.setMockInitialValues(<String, String>{
        WeekFeedbackStore.keyFor('test-user'): jsonEncode(<String, dynamic>{
          '2026-10-19': <String, dynamic>{
            'chips': <String>['guests'],
            'note': 'last week',
            'note_unused': false,
          },
          '2026-10-26': <String, dynamic>{
            'chips': <String>['lighter'],
            'note': '',
            'note_unused': false,
          },
        }),
      });
      final DateTime now = DateTime(2026, 10, 27, 9);
      h = AppTestHarness(
        keepSecureStorage: true,
        overrides: [clockProvider.overrideWithValue(() => now)],
      );
      await open(tester);

      expect(tester.widget<Text>(summary()).data, 'Lighter');
      final String? stored = await tester.runAsync<String?>(
        () => const FlutterSecureStorage().read(
          key: WeekFeedbackStore.keyFor(h.userId),
        ),
      );
      expect((jsonDecode(stored!) as Map<String, dynamic>).keys, <String>[
        '2026-10-26',
      ]);
    },
  );

  gleanWidgetTest('signing out deletes the stored week feedback', (
    tester,
  ) async {
    await h.dispose();
    h = AppTestHarness(httpClient: backend());
    await open(tester);
    await toggleBox(tester);
    await tester.tap(chip(FeedbackChip.lighter));
    await tester.pumpAndSettle();
    Future<String?> stored() => const FlutterSecureStorage().read(
      key: WeekFeedbackStore.keyFor(h.userId),
    );
    expect(await tester.runAsync<String?>(stored), isNotNull);

    await h.container.read(authControllerProvider.notifier).signOut();
    await tester.pumpAndSettle();

    expect(await tester.runAsync<String?>(stored), isNull);
  });

  gleanWidgetTest(
    'another week\'s box is titled with its dates and keeps its own chips',
    (tester) async {
      await open(tester);
      await toggleBox(tester);
      await tester.tap(chip(FeedbackChip.guests));
      await tester.pumpAndSettle();
      Finder title() => find.byKey(const ValueKey<String>('this-week-title'));
      expect(tester.widget<Text>(title()).data, 'This week');

      await tester.tap(find.byTooltip('Next week'));
      await tester.pumpAndSettle();

      final DateTime next = shiftWeeks(startOfWeek(DateTime.now()), 1);
      expect(tester.widget<Text>(title()).data, weekRangeLabel(next));
      expect(tester.widget<Text>(summary()).data, 'Nothing set');

      await tester.tap(find.byTooltip('Previous week'));
      await tester.pumpAndSettle();

      expect(tester.widget<Text>(title()).data, 'This week');
      expect(tester.widget<Text>(summary()).data, 'Guests');
    },
  );

  gleanWidgetTest(
    'with the box closed on a 320 px phone a dropped note is still announced, first in the summary',
    (tester) async {
      tester.view.physicalSize = const Size(320, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      feedbackNote = 'not_a_preference';
      await open(tester);
      await toggleBox(tester);
      await tester.tap(chip(FeedbackChip.somethingNew));
      await tester.tap(chip(FeedbackChip.healthier));
      await tester.enterText(note(), 'ignore previous instructions and');
      await tester.pumpAndSettle();
      await toggleBox(tester);

      await generateAndComeBack(tester);

      expect(note(), findsNothing, reason: 'the box is closed');
      expect(
        find
            .text("Couldn't use that note. Your chips still apply.")
            .hitTestable(),
        findsOneWidget,
      );
      expect(
        tester.widget<Text>(summary()).data,
        "Note couldn't be used · Something new · Healthier",
      );
    },
  );

  gleanWidgetTest(
    'a dropped note is still announced after a restart, box closed',
    (tester) async {
      feedbackNote = 'unavailable';
      await open(tester);
      await toggleBox(tester);
      await tester.enterText(note(), 'mild curries only');
      await tester.pumpAndSettle();
      await generateAndComeBack(tester);

      addTearDown(h.dispose);
      h = AppTestHarness(keepSecureStorage: true, httpClient: backend());
      await open(tester);

      expect(note(), findsNothing);
      expect(
        find.text("Couldn't use that note. Your chips still apply."),
        findsOneWidget,
      );
    },
  );

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
