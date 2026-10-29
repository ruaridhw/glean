import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/data/providers/repository_providers.dart';

import '../../../support/fake_interview_backend.dart';
import '../../../support/harness.dart';

void main() {
  setUpAll(registerInterviewFallbacks);

  testWidgets(
    'retake prepopulates saved facts and cancellation leaves them saved',
    (tester) async {
      final backend = FakeInterviewBackend(<ScriptedResponse>[
        questionResponse(
          turn: 1,
          field: 'household',
          text: 'Who eats with you?',
        ),
      ])..attach();
      final harness = AppTestHarness(httpClient: backend.client);
      addTearDown(harness.dispose);
      await harness.container
          .read(householdProfileRepositoryProvider)
          .save(
            userId: harness.userId,
            profile: const HouseholdProfile(household: 'Two adults'),
          );
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await harness.pumpAt(tester, '/settings/profile');
      await tester.pumpAndSettle();
      expect(find.byType(TextField), findsNothing);
      await tester.ensureVisible(find.text('Retake your taste interview'));
      await tester.tap(find.text('Retake your taste interview'));
      await tester.pumpAndSettle();
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller!.text,
        'Two adults',
      );
      await tester.enterText(find.byType(TextField), 'One adult');
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(
        (await harness.container
                .read(householdProfileRepositoryProvider)
                .get(harness.userId))!
            .household,
        'Two adults',
      );
    },
  );
}
