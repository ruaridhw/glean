// The household profile is the one thing the taste interview leaves behind, so the repository has to keep
// exactly what the interview confirmed: one row per user, the profile as versioned JSON, and a timestamp.
import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/data/repositories/household_profile_repository.dart';

import 'fixture.dart';

const String _userId = 'user-1';

/// Lets drift's query streams deliver, without depending on how many turns of the event loop that takes.
Future<void> _settle() async {
  for (int turn = 0; turn < 5; turn++) {
    await Future<void>.delayed(Duration.zero);
  }
}

void main() {
  late GleanDatabase db;
  late HouseholdProfileRepository profiles;

  setUp(() {
    db = createTestDatabase();
    profiles = HouseholdProfileRepository(db);
  });
  tearDown(() => db.close());

  const HouseholdProfile answered = HouseholdProfile(
    favouriteMeals: <FavouriteMeal>[
      FavouriteMeal(text: 'katsu curry', recipeId: 'rec_1'),
    ],
    dislikedIngredients: <String>['mushrooms'],
    spiceTolerance: SpiceTolerance.mild,
    habits: 'Quick weeknights',
    household: 'Two adults',
  );

  test('a user with no interview yet has no profile', () async {
    expect(await profiles.get(_userId), isNull);
    expect(await profiles.watch(_userId).first, isNull);
  });

  test('a saved profile reads back with every field, and its stored JSON is '
      'the versioned document', () async {
    await profiles.save(userId: _userId, profile: answered);

    final HouseholdProfile? saved = await profiles.get(_userId);
    expect(saved, isNotNull);
    expect(saved!.toJson(), answered.toJson());
    expect(saved.favouriteMeals.single.recipeId, 'rec_1');
    expect(saved.interviewedAt, isNull, reason: 'the interview sets this');

    final HouseholdProfileRow row = await db
        .select(db.householdProfiles)
        .getSingle();
    expect(row.userId, _userId);
    expect(
      HouseholdProfile.decode(row.profileJson)!.toJson(),
      answered.toJson(),
    );
    expect(row.updatedAt, isNotEmpty);
  });

  test('saving again replaces the profile instead of adding a row, so one '
      'user never has two', () async {
    await profiles.save(userId: _userId, profile: answered);
    await profiles.save(
      userId: _userId,
      profile: const HouseholdProfile(household: 'Two adults, one guest'),
    );

    expect(await db.select(db.householdProfiles).get(), hasLength(1));
    expect((await profiles.get(_userId))!.household, 'Two adults, one guest');
  });

  test('the profile is per user', () async {
    await profiles.save(userId: _userId, profile: answered);
    expect(await profiles.get('user-2'), isNull);

    await profiles.save(
      userId: 'user-2',
      profile: const HouseholdProfile(household: 'Just me'),
    );
    expect((await profiles.get(_userId))!.household, 'Two adults');
    expect((await profiles.get('user-2'))!.household, 'Just me');
  });

  test('the watch stream re-emits when the interview confirms', () async {
    final List<HouseholdProfile?> seen = <HouseholdProfile?>[];
    final StreamSubscription<HouseholdProfile?> subscription = profiles
        .watch(_userId)
        .listen(seen.add);
    addTearDown(subscription.cancel);
    await _settle();
    expect(seen, <HouseholdProfile?>[null]);

    await profiles.save(userId: _userId, profile: answered);
    await _settle();

    expect(seen.last?.habits, 'Quick weeknights');
  });

  test('a column this build cannot read reads as no profile rather than '
      'failing every screen that asks', () async {
    await db
        .into(db.householdProfiles)
        .insert(
          HouseholdProfilesCompanion.insert(
            userId: _userId,
            profileJson: '{"version":',
            updatedAt: '2026-10-24T10:00:00.000',
          ),
        );

    expect(await profiles.get(_userId), isNull);
    expect(await profiles.watch(_userId).first, isNull);
  });
}
