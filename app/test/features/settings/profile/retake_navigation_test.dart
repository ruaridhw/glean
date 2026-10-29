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

void main() {
  setUpAll(registerInterviewFallbacks);
  testWidgets(
    'explicit clear remains clear when reviewed without changing it',
    (tester) async {
      final backend = FakeInterviewBackend([
        questionResponse(
          turn: 1,
          field: 'household',
          text: 'Who eats with you?',
        ),
        {
          ...doneResponse(profile: {'household': ''}),
          'updated_fields': ['household'],
        },
        {
          ...doneResponse(profile: {'household': 'Two adults'}),
          'updated_fields': [],
        },
      ])..attach();
      final harness = AppTestHarness(httpClient: backend.client);
      addTearDown(harness.dispose);
      await open(tester, harness);
      await tester.ensureVisible(find.text('Clear this answer'));
      await tester.tap(find.text('Clear this answer'));
      await tester.pumpAndSettle();
      expect(backend.lastAnswer['clear'], true);
      await tester.tap(find.text('Review answers again'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
      expect(
        backend.lastAnswer['clear'],
        true,
        reason: 'Review with no change must retain explicit removal',
      );
    },
  );
  testWidgets('screened-out correction tells the household it was not used', (
    tester,
  ) async {
    final backend = FakeInterviewBackend([
      questionResponse(turn: 1, field: 'household', text: 'Who eats with you?'),
      {
        ...doneResponse(
          profile: {'household': 'Two adults'},
          droppedAnswer: true,
        ),
        'updated_fields': [],
      },
    ])..attach();
    final harness = AppTestHarness(httpClient: backend.client);
    addTearDown(harness.dispose);
    await open(tester, harness);
    await tester.enterText(find.byType(TextField), 'A rejected correction');
    await tester.tap(find.text('Continue'));
    await tester.pumpAndSettle();
    expect(
      find.textContaining("Couldn't use"),
      findsAtLeastNWidgets(1),
      reason: 'Rejected answer must not silently disappear',
    );
  });
  testWidgets('text plus selected options survive a review round trip', (
    tester,
  ) async {
    final backend = FakeInterviewBackend([
      questionResponse(
        turn: 1,
        field: 'household',
        text: 'Who eats with you?',
        options: ['Guests'],
      ),
      {
        ...doneResponse(profile: {'household': 'Two adults; Guests'}),
        'updated_fields': ['household'],
      },
    ])..attach();
    final harness = AppTestHarness(httpClient: backend.client);
    addTearDown(harness.dispose);
    await open(tester, harness);
    await tester.tap(find.text('Guests'));
    await tester.tap(find.text('Continue'));
    await tester.pumpAndSettle();
    expect(backend.lastAnswer['options'], ['Guests']);
    await tester.tap(find.text('Review answers again'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Continue'));
    await tester.pumpAndSettle();
    expect(
      backend.lastAnswer['options'],
      ['Guests'],
      reason: 'Unchanged review must preserve selected preference',
    );
  });
}
