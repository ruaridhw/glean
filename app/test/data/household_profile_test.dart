// The household profile is versioned JSON: it travels to `POST /profile/interview` as `draft_profile`, comes
// back as `profile`, and is stored in `household_profiles.profile_json`. The shape is the contract, so the
// tests below pin the JSON itself rather than only the Dart fields, and prove a document written by a
// different build is read without throwing.
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/household_profile.dart';

/// A profile using every field, built from the contract's own JSON so the test states the wire shape once.
const Map<String, dynamic> _full = <String, dynamic>{
  'version': 1,
  'favourite_meals': <Map<String, dynamic>>[
    <String, dynamic>{'text': 'katsu curry', 'recipe_id': 'rec_1'},
    <String, dynamic>{'text': 'fish pie', 'recipe_id': null},
  ],
  'loved_ingredients': <String>['miso', 'prawns'],
  'disliked_ingredients': <String>['mushrooms'],
  'cuisines_liked': <String>['Japanese', 'Indian'],
  'cuisines_avoided': <String>['Thai'],
  'protein_targets': <Map<String, dynamic>>[
    <String, dynamic>{
      'protein': 'fish',
      'min_per_week': 2,
      'max_per_week': null,
    },
    <String, dynamic>{
      'protein': 'chicken',
      'min_per_week': null,
      'max_per_week': 1,
    },
  ],
  'spice_tolerance': 'medium',
  'habits': 'Quick weeknights, a batch cook at the weekend',
  'household': 'Two adults, two kids',
  'notes': <Map<String, dynamic>>[
    <String, dynamic>{
      'date': '2026-10-24',
      'text': 'Prefers rice over pasta midweek',
      'source': 'feedback',
    },
  ],
  'interviewed_at': '2026-10-24T10:15:00.000Z',
};

void main() {
  test(
    'a profile round-trips through JSON exactly as the contract states it',
    () {
      final HouseholdProfile profile = HouseholdProfile.fromJson(_full);

      expect(profile.version, 1);
      expect(profile.favouriteMeals, hasLength(2));
      expect(profile.favouriteMeals.first.text, 'katsu curry');
      expect(profile.favouriteMeals.first.recipeId, 'rec_1');
      expect(profile.favouriteMeals.last.recipeId, isNull);
      expect(profile.lovedIngredients, <String>['miso', 'prawns']);
      expect(profile.dislikedIngredients, <String>['mushrooms']);
      expect(profile.cuisinesLiked, <String>['Japanese', 'Indian']);
      expect(profile.cuisinesAvoided, <String>['Thai']);
      expect(profile.proteinTargets, hasLength(2));
      expect(profile.proteinTargets.first.protein, 'fish');
      expect(profile.proteinTargets.first.minPerWeek, 2);
      expect(profile.proteinTargets.first.maxPerWeek, isNull);
      expect(profile.proteinTargets.last.maxPerWeek, 1);
      expect(profile.spiceTolerance, SpiceTolerance.medium);
      expect(profile.habits, 'Quick weeknights, a batch cook at the weekend');
      expect(profile.household, 'Two adults, two kids');
      expect(profile.notes.single.date, '2026-10-24');
      expect(profile.notes.single.text, 'Prefers rice over pasta midweek');
      expect(profile.notes.single.source, ProfileNoteSource.feedback);
      expect(profile.interviewedAt, DateTime.utc(2026, 10, 24, 10, 15));

      expect(profile.toJson(), _full);
      expect(HouseholdProfile.decode(profile.encode())!.toJson(), _full);
    },
  );

  test('an empty profile carries every key the contract names', () {
    const HouseholdProfile profile = HouseholdProfile();

    expect(profile.version, HouseholdProfile.currentVersion);
    expect(profile.toJson(), <String, dynamic>{
      'version': 1,
      'favourite_meals': <dynamic>[],
      'loved_ingredients': <dynamic>[],
      'disliked_ingredients': <dynamic>[],
      'cuisines_liked': <dynamic>[],
      'cuisines_avoided': <dynamic>[],
      'protein_targets': <dynamic>[],
      'spice_tolerance': null,
      'habits': '',
      'household': '',
      'notes': <dynamic>[],
      'interviewed_at': null,
    });
  });

  test('missing keys fall back to an empty profile rather than throwing', () {
    final HouseholdProfile profile = HouseholdProfile.fromJson(
      <String, dynamic>{'version': 1},
    );

    expect(profile.favouriteMeals, isEmpty);
    expect(profile.lovedIngredients, isEmpty);
    expect(profile.spiceTolerance, isNull);
    expect(profile.habits, '');
    expect(profile.household, '');
    expect(profile.notes, isEmpty);
    expect(profile.interviewedAt, isNull);
  });

  test('a document from a newer build still reads: unknown keys and versions '
      'are tolerated, and the parts this build knows survive', () {
    final HouseholdProfile profile = HouseholdProfile.fromJson(
      <String, dynamic>{
        'version': 2,
        // A field only the newer build has.
        'food_rules': <String>['no nuts in packed lunches'],
        'disliked_ingredients': <String>['olives'],
        'spice_tolerance': 'inferno',
      },
    );

    expect(profile.version, 2);
    expect(profile.dislikedIngredients, <String>['olives']);
    expect(profile.spiceTolerance, isNull, reason: 'not a value it knows');
    expect(profile.toJson().containsKey('food_rules'), isFalse);
  });

  test('malformed entries are skipped, so one bad field never loses the rest '
      'of an answer', () {
    final HouseholdProfile profile = HouseholdProfile.fromJson(
      <String, dynamic>{
        'version': 1,
        'favourite_meals': <dynamic>[
          'just a string',
          <String, dynamic>{'recipe_id': 'rec_2'},
          <String, dynamic>{'text': 'dal', 'recipe_id': null},
        ],
        'loved_ingredients': <dynamic>['miso', 42, null],
        'protein_targets': <dynamic>[
          <String, dynamic>{'protein': 'fish'},
          <String, dynamic>{'min_per_week': 2},
        ],
        'notes': <dynamic>[
          <String, dynamic>{'date': '2026-10-24'},
          <String, dynamic>{
            'date': '2026-10-25',
            'text': 'Likes it hot',
            'source': 'interview',
          },
        ],
        'interviewed_at': 'not a date',
      },
    );

    expect(profile.favouriteMeals.single.text, 'dal');
    expect(profile.lovedIngredients, <String>['miso']);
    expect(profile.proteinTargets.single.protein, 'fish');
    expect(profile.notes.single.source, ProfileNoteSource.interview);
    expect(profile.notes.single.date, '2026-10-25');
    expect(profile.interviewedAt, isNull);
  });

  test('a number the wire should never carry reads as no value instead of '
      'throwing', () {
    final HouseholdProfile profile = HouseholdProfile.fromJson(
      <String, dynamic>{
        'version': 1,
        'protein_targets': <dynamic>[
          <String, dynamic>{
            'protein': 'fish',
            'min_per_week': 1e400,
            'max_per_week': 2,
          },
        ],
      },
    );

    expect(profile.proteinTargets.single.minPerWeek, isNull);
    expect(profile.proteinTargets.single.maxPerWeek, 2);

    // The whole document, as it comes out of the stored column.
    final HouseholdProfile? decoded = HouseholdProfile.decode(
      '{"version": 1e400}',
    );
    expect(decoded, isNotNull);
    expect(decoded!.version, HouseholdProfile.currentVersion);
  });

  test('a stored column that is not a profile at all reads as no profile', () {
    expect(HouseholdProfile.decode(''), isNull);
    expect(HouseholdProfile.decode('not json'), isNull);
    expect(HouseholdProfile.decode('[1, 2, 3]'), isNull);
  });
  test('copyWith changes only the fields it names, and an edited profile '
      'keeps its version and interview time', () {
    final HouseholdProfile full = HouseholdProfile.fromJson(_full);

    final HouseholdProfile edited = full.copyWith(
      dislikedIngredients: <String>['mushrooms', 'olives'],
      habits: 'Leftovers on Mondays',
    );

    expect(edited.dislikedIngredients, <String>['mushrooms', 'olives']);
    expect(edited.habits, 'Leftovers on Mondays');
    final Map<String, dynamic> rest = edited.toJson()
      ..remove('disliked_ingredients')
      ..remove('habits');
    final Map<String, dynamic> original = full.toJson()
      ..remove('disliked_ingredients')
      ..remove('habits');
    expect(rest, original);
  });

  test('spice tolerance can be set and cleared again', () {
    final HouseholdProfile full = HouseholdProfile.fromJson(_full);

    expect(
      full.withSpiceTolerance(SpiceTolerance.hot).spiceTolerance,
      SpiceTolerance.hot,
    );
    final HouseholdProfile cleared = full.withSpiceTolerance(null);
    expect(cleared.spiceTolerance, isNull);
    expect(cleared.habits, full.habits);
  });

  test('a profile is empty only when every answer and note is', () {
    expect(const HouseholdProfile().isEmpty, isTrue);
    expect(HouseholdProfile.fromJson(_full).isEmpty, isFalse);
    for (final HouseholdProfile one in <HouseholdProfile>[
      const HouseholdProfile(
        favouriteMeals: <FavouriteMeal>[FavouriteMeal(text: 'dal')],
      ),
      const HouseholdProfile(lovedIngredients: <String>['miso']),
      const HouseholdProfile(dislikedIngredients: <String>['olives']),
      const HouseholdProfile(cuisinesLiked: <String>['Indian']),
      const HouseholdProfile(cuisinesAvoided: <String>['Thai']),
      const HouseholdProfile(
        proteinTargets: <ProteinTarget>[ProteinTarget(protein: 'fish')],
      ),
      const HouseholdProfile(spiceTolerance: SpiceTolerance.none),
      const HouseholdProfile(habits: 'Leftovers'),
      const HouseholdProfile(household: 'Just me'),
      const HouseholdProfile(
        notes: <ProfileNote>[
          ProfileNote(
            date: '2026-10-24',
            text: 'Likes rice',
            source: ProfileNoteSource.feedback,
          ),
        ],
      ),
    ]) {
      expect(one.isEmpty, isFalse, reason: one.encode());
    }
  });
}
