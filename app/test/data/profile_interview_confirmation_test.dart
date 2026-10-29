import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/data/repositories/household_profile_repository.dart';

import 'fixture.dart';

void main() {
  test(
    'confirm overlays only interview targets onto the latest profile',
    () async {
      final db = createTestDatabase();
      addTearDown(db.close);
      final profiles = HouseholdProfileRepository(db);
      const baseline = HouseholdProfile(
        household: 'Two adults',
        habits: 'Quick dinners',
      );
      await profiles.save(userId: 'user', profile: baseline);
      const note = ProfileNote(
        date: '2026-10-29',
        text: 'Rice on Fridays',
        source: ProfileNoteSource.feedback,
      );
      await profiles.save(
        userId: 'user',
        profile: const HouseholdProfile(
          household: 'Two adults',
          habits: 'Slow weekends',
          notes: <ProfileNote>[note],
          dismissedNotes: <String>['No pasta'],
        ),
      );
      await profiles.confirmInterview(
        userId: 'user',
        baseline: baseline,
        candidate: const HouseholdProfile(household: 'One adult'),
        fields: <String>{'household'},
      );
      final saved = (await profiles.get('user'))!;
      expect(saved.household, 'One adult');
      expect(saved.habits, 'Slow weekends');
      expect(saved.notes.single.text, 'Rice on Fridays');
      expect(saved.dismissedNotes, <String>['No pasta']);
    },
  );

  test(
    'a stale intentional clear refuses to overwrite a newer answer',
    () async {
      final db = createTestDatabase();
      addTearDown(db.close);
      final profiles = HouseholdProfileRepository(db);
      const baseline = HouseholdProfile(household: 'Two adults');
      await profiles.save(
        userId: 'user',
        profile: const HouseholdProfile(household: 'Three adults'),
      );
      await expectLater(
        profiles.confirmInterview(
          userId: 'user',
          baseline: baseline,
          candidate: const HouseholdProfile(),
          fields: <String>{'household'},
        ),
        throwsA(isA<ProfileInterviewConflict>()),
      );
      expect((await profiles.get('user'))!.household, 'Three adults');
    },
  );
}
