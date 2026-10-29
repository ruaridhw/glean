import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/data/providers/repository_providers.dart';

import '../../../support/fake_interview_backend.dart';
import '../../../support/harness.dart';

Future<void> open(WidgetTester tester, AppTestHarness harness) async {
  await tester.binding.setSurfaceSize(const Size(390, 844));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await harness.container
      .read(householdProfileRepositoryProvider)
      .save(
        userId: harness.userId,
        profile: const HouseholdProfile(household: 'Two adults'),
      );
  await harness.pumpAt(tester, '/settings/profile');
  await tester.pumpAndSettle();
  await tester.ensureVisible(find.text('Retake your taste interview'));
  await tester.tap(find.text('Retake your taste interview'));
  await tester.pumpAndSettle();
}

Map<String, dynamic> candidate(List<String> fields) => <String, dynamic>{
  ...doneResponse(profile: <String, dynamic>{'household': ''}),
  'updated_fields': fields,
};

void main() {
  setUpAll(registerInterviewFallbacks);

  testWidgets(
    'explicit clear survives request retry and saves only on confirmation',
    (tester) async {
      final backend = FakeInterviewBackend(<ScriptedResponse>[
        questionResponse(
          turn: 1,
          field: 'household',
          text: 'Who eats with you?',
        ),
        503,
        candidate(<String>['household']),
      ])..attach();
      final harness = AppTestHarness(httpClient: backend.client);
      addTearDown(harness.dispose);
      await open(tester, harness);
      final profiles = harness.container.read(
        householdProfileRepositoryProvider,
      );
      await tester.ensureVisible(find.text('Clear this answer'));
      await tester.tap(find.text('Clear this answer'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Retry'));
      await tester.tap(find.text('Retry'));
      await tester.pumpAndSettle();
      expect(backend.requests.last['retake'], isTrue);
      expect(backend.lastAnswer['clear'], isTrue);
      expect(backend.lastAnswer['text'], isNull);
      expect(backend.lastAnswer['options'], isEmpty);
      expect(backend.lastAnswer['skipped'], isFalse);
      expect(find.text('Does this sound like you?'), findsOneWidget);
      expect((await profiles.get(harness.userId))!.household, 'Two adults');
      await profiles.update(
        userId: harness.userId,
        change: (current) => current.withKeptNote(
          const ProfileNote(
            date: '2026-10-29',
            text: 'Rice on Friday',
            source: ProfileNoteSource.feedback,
          ),
        ),
      );
      await tester.tap(find.text('Save profile'));
      await tester.pumpAndSettle();
      final saved = (await profiles.get(harness.userId))!;
      expect(saved.household, isEmpty);
      expect(saved.notes.single.text, 'Rice on Friday');
      expect(find.text('Retake your taste interview'), findsOneWidget);
    },
  );

  testWidgets('empty input is a skip, not an implicit removal', (tester) async {
    final backend = FakeInterviewBackend(<ScriptedResponse>[
      questionResponse(turn: 1, field: 'household', text: 'Who eats with you?'),
      candidate(<String>[]),
    ])..attach();
    final harness = AppTestHarness(httpClient: backend.client);
    addTearDown(harness.dispose);
    await open(tester, harness);
    final profiles = harness.container.read(householdProfileRepositoryProvider);
    await tester.enterText(find.byType(TextField), '');
    await tester.tap(find.text('Continue'));
    await tester.pumpAndSettle();
    expect(backend.lastAnswer['skipped'], isTrue);
    expect(backend.lastAnswer['clear'], isNot(true));
    await tester.tap(find.text('Save profile'));
    await tester.pumpAndSettle();
    expect((await profiles.get(harness.userId))!.household, 'Two adults');
  });

  testWidgets(
    'a failed save retains the draft and a retry confirms without another API call',
    (tester) async {
      final backend = FakeInterviewBackend(<ScriptedResponse>[
        questionResponse(
          turn: 1,
          field: 'household',
          text: 'Who eats with you?',
        ),
        candidate(<String>['household']),
      ])..attach();
      final harness = AppTestHarness(httpClient: backend.client);
      addTearDown(harness.dispose);
      await open(tester, harness);
      await tester.ensureVisible(find.text('Clear this answer'));
      await tester.tap(find.text('Clear this answer'));
      await tester.pumpAndSettle();
      await harness.failInsertsOn('household_profiles');
      await tester.tap(find.text('Save profile'));
      await tester.pumpAndSettle();
      expect(
        find.text(
          'Could not save your profile. Your saved profile is unchanged. Try again.',
        ),
        findsOneWidget,
      );
      expect(
        (await harness.container
                .read(householdProfileRepositoryProvider)
                .get(harness.userId))!
            .household,
        'Two adults',
      );
      await harness.db.customStatement(
        'DROP TRIGGER fail_insert_household_profiles',
      );
      await tester.tap(find.text('Save profile'));
      await tester.pumpAndSettle();
      expect(
        (await harness.container
                .read(householdProfileRepositoryProvider)
                .get(harness.userId))!
            .household,
        isEmpty,
      );
      expect(backend.requests, hasLength(2));
    },
  );

  testWidgets(
    'stale clear asks to start again rather than overwrite newer answers',
    (tester) async {
      final backend = FakeInterviewBackend(<ScriptedResponse>[
        questionResponse(
          turn: 1,
          field: 'household',
          text: 'Who eats with you?',
        ),
        candidate(<String>['household']),
      ])..attach();
      final harness = AppTestHarness(httpClient: backend.client);
      addTearDown(harness.dispose);
      await open(tester, harness);
      await tester.ensureVisible(find.text('Clear this answer'));
      await tester.tap(find.text('Clear this answer'));
      await tester.pumpAndSettle();
      final profiles = harness.container.read(
        householdProfileRepositoryProvider,
      );
      await profiles.save(
        userId: harness.userId,
        profile: const HouseholdProfile(household: 'Three adults'),
      );
      await tester.tap(find.text('Save profile'));
      await tester.pumpAndSettle();
      expect(find.text('Start again'), findsOneWidget);
      expect((await profiles.get(harness.userId))!.household, 'Three adults');
    },
  );
}
