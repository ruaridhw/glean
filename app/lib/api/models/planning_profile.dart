/// The household profile as `POST /meal-plan` and `POST /meal-plan/sessions` send it, as `profile`.
///
/// The backend refuses (422) a profile past these bounds rather than clipping it, so the app clips on the way out:
/// the first [maxPlanningListEntries] entries of each list, each string at most [maxPlanningTextChars] code points
/// (a favourite meal [maxPlanningFavouriteChars], because it is matched against corpus titles),
/// the two free-text fields at most [maxPlanningParagraphChars], and only the newest [maxPlanningNotes] notes, each
/// at most [maxPlanningNoteChars]. Code points, not UTF-16 units, because that is what the backend counts. The
/// numbers mirror `PlanningProfile` in the backend's `meal_plan/schemas.py`.
library;

import '../../data/models/household_profile.dart';

const int maxPlanningListEntries = 20;
const int maxPlanningTextChars = 60;
const int maxPlanningFavouriteChars = 120;
const int maxPlanningParagraphChars = 500;
const int maxPlanningNotes = 20;
const int maxPlanningNoteChars = 200;

/// [profile] bounded for the wire, or `null` when there is no profile or nothing in it (the interview was skipped
/// and nothing was added since): the planner then plans as it did before profiles existed.
Map<String, dynamic>? planningProfileJson(HouseholdProfile? profile) {
  if (profile == null || profile.isEmpty) return null;
  final List<ProfileNote> newest = <ProfileNote>[...profile.notes]
    ..sort((ProfileNote a, ProfileNote b) => b.date.compareTo(a.date));
  return <String, dynamic>{
    'version': profile.version,
    'favourite_meals': <Map<String, dynamic>>[
      for (final FavouriteMeal meal in profile.favouriteMeals.take(
        maxPlanningListEntries,
      ))
        <String, dynamic>{
          'text': _clip(meal.text, maxPlanningFavouriteChars),
          'recipe_id': meal.recipeId,
        },
    ],
    'loved_ingredients': _list(profile.lovedIngredients),
    'disliked_ingredients': _list(profile.dislikedIngredients),
    'cuisines_liked': _list(profile.cuisinesLiked),
    'cuisines_avoided': _list(profile.cuisinesAvoided),
    'protein_targets': <Map<String, dynamic>>[
      for (final ProteinTarget target in profile.proteinTargets.take(
        maxPlanningListEntries,
      ))
        target.toJson(),
    ],
    'spice_tolerance': profile.spiceTolerance?.name,
    'habits': _clip(profile.habits, maxPlanningParagraphChars),
    'household': _clip(profile.household, maxPlanningParagraphChars),
    'notes': <Map<String, dynamic>>[
      for (final ProfileNote note in newest.take(maxPlanningNotes))
        <String, dynamic>{
          'date': note.date,
          'text': _clip(note.text, maxPlanningNoteChars),
          'source': note.source.name,
        },
    ],
  };
}

List<String> _list(List<String> values) => <String>[
  for (final String value in values.take(maxPlanningListEntries))
    _clip(value, maxPlanningTextChars),
];

String _clip(String text, int codePoints) {
  final List<int> runes = text.runes.toList();
  return runes.length <= codePoints
      ? text
      : String.fromCharCodes(runes.take(codePoints)).trimRight();
}
