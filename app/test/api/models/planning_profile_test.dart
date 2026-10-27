// The household profile as Generate sends it: null when there is nothing to send, bounded to what the backend accepts.
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/models/planning_profile.dart';
import 'package:glean/data/models/household_profile.dart';

void main() {
  test('no profile, or an empty one, sends null', () {
    expect(planningProfileJson(null), isNull);
    expect(planningProfileJson(const HouseholdProfile()), isNull);
  });

  test('a real profile is sent as the contract shape', () {
    final Map<String, dynamic>? json = planningProfileJson(
      const HouseholdProfile(
        favouriteMeals: <FavouriteMeal>[
          FavouriteMeal(text: 'Fish pie', recipeId: 'rec_pie'),
        ],
        dislikedIngredients: <String>['mushrooms'],
        cuisinesLiked: <String>['Italian'],
        proteinTargets: <ProteinTarget>[
          ProteinTarget(protein: 'fish', minPerWeek: 1),
        ],
        spiceTolerance: SpiceTolerance.mild,
        habits: 'Quick weeknights',
      ),
    );

    expect(json, isNotNull);
    expect(json!['disliked_ingredients'], <String>['mushrooms']);
    expect(json['favourite_meals'], <Map<String, dynamic>>[
      <String, dynamic>{'text': 'Fish pie', 'recipe_id': 'rec_pie'},
    ]);
    expect(json['protein_targets'], <Map<String, dynamic>>[
      <String, dynamic>{
        'protein': 'fish',
        'min_per_week': 1,
        'max_per_week': null,
      },
    ]);
    expect(json['spice_tolerance'], 'mild');
    expect(json['habits'], 'Quick weeknights');
    expect(json.containsKey('interviewed_at'), isFalse);
  });

  test('lists keep their first twenty entries, each at most sixty code points', () {
    final Map<String, dynamic> json = planningProfileJson(
      HouseholdProfile(
        lovedIngredients: <String>[for (int n = 0; n < 25; n++) 'item $n'],
        dislikedIngredients: <String>['🍄' * 70],
        favouriteMeals: <FavouriteMeal>[
          for (int n = 0; n < 25; n++) FavouriteMeal(text: 'x' * 150),
        ],
      ),
    )!;

    expect(json['loved_ingredients'], hasLength(maxPlanningListEntries));
    expect((json['loved_ingredients'] as List<String>).last, 'item 19');
    // An emoji is one code point however many UTF-16 units it takes: the backend counts code points.
    expect(
      (json['disliked_ingredients'] as List<String>).single.runes,
      hasLength(60),
    );
    final List<Map<String, dynamic>> meals =
        (json['favourite_meals'] as List<Map<String, dynamic>>);
    expect(meals, hasLength(20));
    // A favourite may be as long as a corpus title, which it is matched against: 120, not the lists' 60.
    expect((meals.first['text'] as String).length, 120);
  });

  test('free text is at most five hundred code points', () {
    final Map<String, dynamic> json = planningProfileJson(
      HouseholdProfile(habits: 'h' * 600, household: 'é' * 501),
    )!;

    expect((json['habits'] as String).runes, hasLength(500));
    expect((json['household'] as String).runes, hasLength(500));
  });

  test(
    'only the newest twenty notes go, each at most two hundred code points',
    () {
      final Map<String, dynamic> json = planningProfileJson(
        HouseholdProfile(
          notes: <ProfileNote>[
            for (int day = 1; day <= 25; day++)
              ProfileNote(
                date: '2026-10-${day.toString().padLeft(2, '0')}',
                text: 'n' * 250,
                source: ProfileNoteSource.feedback,
              ),
          ],
        ),
      )!;

      final List<Map<String, dynamic>> notes =
          json['notes'] as List<Map<String, dynamic>>;
      expect(notes, hasLength(maxPlanningNotes));
      expect(notes.first['date'], '2026-10-25');
      expect(notes.last['date'], '2026-10-06');
      expect((notes.first['text'] as String).length, 200);
    },
  );

  test('a protein target the backend does not know is left out, not sent', () {
    // The backend's main_protein is an enum, so an unknown value would fail the whole Generate with a 422.
    final Map<String, dynamic> json = planningProfileJson(
      const HouseholdProfile(
        proteinTargets: <ProteinTarget>[
          ProteinTarget(protein: 'goat', minPerWeek: 1),
          ProteinTarget(protein: 'fish', minPerWeek: 2),
        ],
      ),
    )!;

    expect(json['protein_targets'], <Map<String, dynamic>>[
      <String, dynamic>{
        'protein': 'fish',
        'min_per_week': 2,
        'max_per_week': null,
      },
    ]);
  });
}
