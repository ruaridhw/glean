import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/data/providers/repository_providers.dart';

import '../../../support/harness.dart';

void main() {
  testWidgets(
    'saved profile shows tastes and independent memory without manual editors',
    (tester) async {
      final harness = AppTestHarness();
      addTearDown(harness.dispose);
      await harness.container
          .read(householdProfileRepositoryProvider)
          .save(
            userId: harness.userId,
            profile: const HouseholdProfile(
              household: 'Two adults',
              habits: 'Quick weeknights',
              lovedIngredients: <String>['miso'],
              cuisinesLiked: <String>['Thai'],
              notes: <ProfileNote>[
                ProfileNote(
                  date: '2026-10-29',
                  text: 'Rice on Friday',
                  source: ProfileNoteSource.feedback,
                ),
              ],
              spiceTolerance: SpiceTolerance.medium,
            ),
          );
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await harness.pumpAt(tester, '/settings/profile');
      await tester.pumpAndSettle();
      expect(find.text('miso, Thai'), findsOneWidget);
      expect(find.text('Also remembered'), findsOneWidget);
      expect(find.text('Rice on Friday'), findsOneWidget);
      expect(find.byType(TextField), findsNothing);
      expect(find.byType(ChoiceChip), findsNothing);
      expect(find.byType(AlertDialog), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('empty profile offers an interview instead of manual fields', (
    tester,
  ) async {
    final harness = AppTestHarness();
    addTearDown(harness.dispose);
    await harness.pumpAt(tester, '/settings/profile');
    await tester.pumpAndSettle();
    expect(find.text('Start your taste interview'), findsOneWidget);
    expect(find.byType(TextField), findsNothing);
  });

  testWidgets('saved facts remain readable at narrow width and large text', (
    tester,
  ) async {
    final harness = AppTestHarness();
    addTearDown(harness.dispose);
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.binding.setSurfaceSize(const Size(320, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await harness.container
        .read(householdProfileRepositoryProvider)
        .save(
          userId: harness.userId,
          profile: const HouseholdProfile(
            household: 'Two adults',
            habits: 'Quick dinners',
          ),
        );
    await harness.pumpAt(tester, '/settings/profile');
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.text('Retake your taste interview'),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    expect(tester.takeException(), isNull);
  });
}
