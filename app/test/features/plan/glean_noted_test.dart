// The "Glean noted" card at the top of the proposal: one row per note the planner offers, each with Keep and ✕.
// Keep appends exactly one note to the household profile; ✕ adds no note and only remembers the dismissal, so
// it is not offered again; nothing reaches the profile's notes without Keep. Seam: the proposal screen over a real database, with the session backend faked at the HTTP client.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/router/app_routes.dart';

import '../../support/harness.dart';
import 'proposal_screen_test.dart'
    show alternative, proposalBackend, suggestion;

const String _rice = 'You prefer rice over pasta midweek.';
const String _kids = "The kids don't like spicy food.";

Map<String, dynamic> _result({List<String> notes = const <String>[]}) =>
    <String, dynamic>{
      'suggestions': <Map<String, dynamic>>[
        suggestion(
          'rec_a',
          title: 'Chicken katsu curry',
          reason: 'Uses up your coriander.',
          alternative: alternative('rec_a_alt', 'Chicken & cashew stir-fry'),
        ),
      ],
      'week_summary': 'Four dinners, one fish, one meat-free.',
      'planned_alternatives': <Map<String, dynamic>>[],
      'degraded': false,
      'profile_notes': <Map<String, dynamic>>[
        for (final String text in notes)
          <String, dynamic>{'text': text, 'evidence': 'rating'},
      ],
    };

String _today() {
  final DateTime now = DateTime.now();
  return '${now.year.toString().padLeft(4, '0')}-'
      '${now.month.toString().padLeft(2, '0')}-'
      '${now.day.toString().padLeft(2, '0')}';
}

Finder _card() => find.byKey(const ValueKey<String>('glean-noted'));

Finder _row(String text) => find.ancestor(
  of: find.text(text),
  matching: find.byKey(ValueKey<String>('glean-noted-$text')),
);

Finder _inRow(String text, Finder finder) =>
    find.descendant(of: _row(text), matching: finder);

void main() {
  Future<AppTestHarness> open(
    WidgetTester tester, {
    List<String> notes = const <String>[_rice, _kids],
  }) async {
    final h = AppTestHarness(
      httpClient: proposalBackend(result: _result(notes: notes)),
    );
    addTearDown(h.dispose);
    await h.pumpAt(tester, AppRoutes.plan.path);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
    await tester.pumpAndSettle();
    return h;
  }

  Future<HouseholdProfile?> profile(AppTestHarness h) =>
      h.container.read(householdProfileRepositoryProvider).get(h.userId);

  gleanWidgetTest(
    'the card sits above the week summary with one row per note, each with '
    'Keep and a dismiss',
    (tester) async {
      await open(tester);

      expect(find.text('Glean noted'), findsOneWidget);
      expect(
        tester.getTopLeft(_card()).dy,
        lessThan(tester.getTopLeft(find.text('This week')).dy),
      );
      for (final String note in <String>[_rice, _kids]) {
        expect(_inRow(note, find.text('Keep')), findsOneWidget);
        expect(_inRow(note, find.byIcon(Icons.close_rounded)), findsOneWidget);
      }
      expect(
        find.text(
          'From your ratings, answers and swap notes. Kept notes are used in future plans.',
        ),
        findsOneWidget,
      );
    },
  );

  gleanWidgetTest('a proposal with no notes shows no card', (tester) async {
    await open(tester, notes: const <String>[]);

    expect(_card(), findsNothing);
    expect(find.text('This week'), findsOneWidget);
  });

  gleanWidgetTest(
    'Keep appends exactly one feedback note to the profile and confirms it',
    (tester) async {
      final h = await open(tester);

      await tester.tap(_inRow(_rice, find.text('Keep')));
      await tester.pumpAndSettle();

      final HouseholdProfile? stored = await profile(h);
      expect(stored, isNotNull);
      expect(stored!.notes, hasLength(1));
      expect(stored.notes.single.text, _rice);
      expect(stored.notes.single.source, ProfileNoteSource.feedback);
      expect(stored.notes.single.date, _today());
      expect(find.text('Kept in your profile'), findsOneWidget);
      expect(_row(_rice), findsNothing);
      expect(_row(_kids), findsOneWidget);
    },
  );

  gleanWidgetTest('Keep adds to the notes the profile already has', (
    tester,
  ) async {
    final h = AppTestHarness(
      httpClient: proposalBackend(result: _result(notes: <String>[_rice])),
    );
    addTearDown(h.dispose);
    await h.container
        .read(householdProfileRepositoryProvider)
        .save(
          userId: h.userId,
          profile: const HouseholdProfile(
            lovedIngredients: <String>['coriander'],
            notes: <ProfileNote>[
              ProfileNote(
                date: '2026-10-01',
                text: 'Cooks for four',
                source: ProfileNoteSource.interview,
              ),
            ],
          ),
        );
    await h.pumpAt(tester, AppRoutes.plan.path);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
    await tester.pumpAndSettle();

    await tester.tap(_inRow(_rice, find.text('Keep')));
    await tester.pumpAndSettle();

    final HouseholdProfile stored = (await profile(h))!;
    expect(stored.notes.map((ProfileNote note) => note.text), <String>[
      'Cooks for four',
      _rice,
    ]);
    expect(stored.lovedIngredients, <String>['coriander']);
  });

  gleanWidgetTest(
    'Keep on a full profile drops the oldest feedback note, never an '
    'interview note',
    (tester) async {
      final h = AppTestHarness(
        httpClient: proposalBackend(result: _result(notes: <String>[_rice])),
      );
      addTearDown(h.dispose);
      await h.container
          .read(householdProfileRepositoryProvider)
          .save(
            userId: h.userId,
            profile: HouseholdProfile(
              notes: <ProfileNote>[
                const ProfileNote(
                  date: '2026-10-01',
                  text: 'Cooks for four',
                  source: ProfileNoteSource.interview,
                ),
                for (int i = 1; i < HouseholdProfile.maxNotes; i++)
                  ProfileNote(
                    date: '2026-10-02',
                    text: 'Feedback $i',
                    source: ProfileNoteSource.feedback,
                  ),
              ],
            ),
          );
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
      await tester.pumpAndSettle();

      await tester.tap(_inRow(_rice, find.text('Keep')));
      await tester.pumpAndSettle();

      final List<String> texts = (await profile(
        h,
      ))!.notes.map((ProfileNote note) => note.text).toList();
      expect(texts, hasLength(HouseholdProfile.maxNotes));
      expect(texts.first, 'Cooks for four');
      expect(texts, isNot(contains('Feedback 1')));
      expect(texts.last, _rice);
    },
  );

  gleanWidgetTest(
    'the dismiss hides the note, adds no note, and remembers it was dismissed',
    (tester) async {
      final h = await open(tester);

      await tester.tap(_inRow(_kids, find.byIcon(Icons.close_rounded)));
      await tester.pumpAndSettle();

      expect(_row(_kids), findsNothing);
      expect(_row(_rice), findsOneWidget);
      final HouseholdProfile stored = (await profile(h))!;
      expect(stored.notes, isEmpty);
      expect(stored.dismissedNotes, <String>[_kids]);
    },
  );

  gleanWidgetTest(
    'a note the profile already holds, or one dismissed before, is not offered '
    'again',
    (tester) async {
      final h = AppTestHarness(
        httpClient: proposalBackend(
          result: _result(
            notes: <String>[_rice, _kids, 'Likes fish on Fridays'],
          ),
        ),
      );
      addTearDown(h.dispose);
      await h.container
          .read(householdProfileRepositoryProvider)
          .save(
            userId: h.userId,
            profile: const HouseholdProfile(
              notes: <ProfileNote>[
                ProfileNote(
                  date: '2026-10-01',
                  text: 'you prefer rice over pasta midweek.',
                  source: ProfileNoteSource.feedback,
                ),
              ],
              dismissedNotes: <String>[_kids],
            ),
          );
      await h.pumpAt(tester, AppRoutes.plan.path);
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Generate'));
      await tester.pumpAndSettle();

      expect(_row(_rice), findsNothing);
      expect(_row(_kids), findsNothing);
      expect(_row('Likes fish on Fridays'), findsOneWidget);
    },
  );

  gleanWidgetTest(
    'a dismiss that cannot be remembered still hides the note and adds none',
    (tester) async {
      final h = await open(tester);
      await h.failInsertsOn('household_profiles');

      await tester.tap(_inRow(_kids, find.byIcon(Icons.close_rounded)));
      await tester.pumpAndSettle();

      expect(_row(_kids), findsNothing);
      expect(_row(_rice), findsOneWidget);
      expect(await profile(h), isNull);
    },
  );

  gleanWidgetTest('the card goes once every note is handled', (tester) async {
    final h = await open(tester);

    await tester.tap(_inRow(_rice, find.text('Keep')));
    await tester.pumpAndSettle();
    expect(_card(), findsOneWidget);
    await tester.tap(_inRow(_kids, find.byIcon(Icons.close_rounded)));
    await tester.pumpAndSettle();

    expect(_card(), findsNothing);
    expect(find.text('Glean noted'), findsNothing);
    final HouseholdProfile stored = (await profile(h))!;
    expect(stored.notes.map((ProfileNote note) => note.text), <String>[_rice]);
    expect(stored.dismissedNotes, <String>[_kids]);
  });

  gleanWidgetTest(
    'leaving the proposal without a Keep writes nothing to the profile',
    (tester) async {
      final h = await open(tester);

      await tester.tap(find.widgetWithText(OutlinedButton, 'Discard'));
      await tester.pumpAndSettle();

      expect(await profile(h), isNull);
    },
  );

  gleanWidgetTest(
    'a Keep that cannot be saved says so and leaves the note to try again',
    (tester) async {
      final h = await open(tester, notes: const <String>[_rice]);
      await h.failInsertsOn('household_profiles');

      await tester.tap(_inRow(_rice, find.text('Keep')));
      await tester.pumpAndSettle();

      expect(find.text("Couldn't keep that note. Try again."), findsOneWidget);
      expect(_row(_rice), findsOneWidget);
      expect(await profile(h), isNull);
    },
  );

  gleanWidgetTest('a local swap leaves the handled notes handled', (
    tester,
  ) async {
    await open(tester);
    await tester.tap(_inRow(_rice, find.byIcon(Icons.close_rounded)));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Swap'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Use alternative'));
    await tester.pumpAndSettle();

    expect(find.text('Chicken & cashew stir-fry'), findsOneWidget);
    expect(_row(_rice), findsNothing);
    expect(_row(_kids), findsOneWidget);
  });

  gleanWidgetTest(
    'each action names its note for a screen reader and is at least 48 dp',
    (tester) async {
      final SemanticsHandle semantics = tester.ensureSemantics();
      await open(tester);

      expect(find.bySemanticsLabel('Keep: $_rice'), findsOneWidget);
      expect(find.bySemanticsLabel('Dismiss: $_rice'), findsOneWidget);
      for (final Finder target in <Finder>[
        _inRow(_rice, find.byType(TextButton)),
        _inRow(_rice, find.byType(IconButton)),
      ]) {
        final Size size = tester.getSize(target);
        expect(size.width, greaterThanOrEqualTo(48));
        expect(size.height, greaterThanOrEqualTo(48));
      }
      expect(
        tester.getSemantics(find.text('Glean noted')),
        matchesSemantics(label: 'Glean noted', isHeader: true),
      );
      semantics.dispose();
    },
  );
}
