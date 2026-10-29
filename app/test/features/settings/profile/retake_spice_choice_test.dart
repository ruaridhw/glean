import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/data/providers/repository_providers.dart';

import '../../../support/fake_interview_backend.dart';
import '../../../support/harness.dart';

void main() {
  setUpAll(registerInterviewFallbacks);
  testWidgets(
    'a new spice choice replaces saved heat and survives review before confirming',
    (tester) async {
      final backend = FakeInterviewBackend(<ScriptedResponse>[
        questionResponse(
          turn: 6,
          id: 'follow-up-6',
          field: 'spice_tolerance',
          text: 'How spicy do you like your food?',
          options: <String>['Not at all', 'Mild', 'Medium', 'Hot'],
        ),
        <String, dynamic>{
          ...doneResponse(
            profile: <String, dynamic>{'spice_tolerance': 'mild'},
          ),
          'updated_fields': <String>['spice_tolerance'],
        },
      ])..attach();
      final harness = AppTestHarness(httpClient: backend.client);
      addTearDown(harness.dispose);
      final profiles = harness.container.read(
        householdProfileRepositoryProvider,
      );
      await profiles.save(
        userId: harness.userId,
        profile: const HouseholdProfile(spiceTolerance: SpiceTolerance.hot),
      );
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await harness.pumpAt(tester, '/settings/profile');
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Retake your taste interview'));
      await tester.tap(find.text('Retake your taste interview'));
      await tester.pumpAndSettle();
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller!.text,
        'hot',
      );
      await tester.ensureVisible(find.text('Mild'));
      await tester.tap(find.text('Mild'));
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
      expect(backend.lastAnswer['options'], <String>['Mild']);
      expect(
        backend.lastAnswer['text'],
        isNull,
        reason: 'The selected heat must replace the saved composer value',
      );
      expect(
        (await profiles.get(harness.userId))!.spiceTolerance,
        SpiceTolerance.hot,
      );
      await tester.tap(find.text('Review answers again'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();
      expect(backend.lastAnswer['options'], <String>['Mild']);
      expect(backend.lastAnswer['text'], isNull);
      await tester.tap(find.text('Save profile'));
      await tester.pumpAndSettle();
      expect(
        (await profiles.get(harness.userId))!.spiceTolerance,
        SpiceTolerance.mild,
      );
    },
  );
}
