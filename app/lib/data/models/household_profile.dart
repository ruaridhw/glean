/// The household profile the taste interview builds: what the household loves, avoids and how it cooks.
///
/// Stored as versioned JSON in one column (`household_profiles.profile_json`) and sent to
/// `POST /profile/interview` as `draft_profile`, so this shape is also the wire contract. [version] is the
/// document's own version, independent of the database schema version: a newer build can add fields (and a
/// later V13-shaped change can add enum sets for the ingredient lists) without a schema bump.
///
/// Reading is deliberately tolerant, because the JSON may have been written by a build this one is not: a
/// missing key reads as empty, an entry of the wrong shape is skipped instead of losing the whole profile, an
/// unknown `spice_tolerance` reads as no answer, and a version this build does not know is carried through
/// unchanged. Nothing here throws on bad input; [decode] reports an unreadable column as `null`.
library;

import 'dart:convert';

/// How much heat the household wants, or `null` when they did not say.
enum SpiceTolerance { none, mild, medium, hot }

/// Where a [ProfileNote] came from: the interview itself, or something the planner inferred from ratings and
/// swap notes (which only ever lands here once the household keeps it).
enum ProfileNoteSource { interview, feedback }

/// One dinner the household would happily eat every fortnight, matched to a corpus recipe when the interview
/// could find it.
class FavouriteMeal {
  const FavouriteMeal({required this.text, this.recipeId});

  factory FavouriteMeal.fromJson(Map<String, dynamic> json) => FavouriteMeal(
    text: _text(json['text'])!,
    recipeId: _text(json['recipe_id']),
  );

  /// What the household called it.
  final String text;

  /// The matched corpus recipe, or `null` when nothing matched — the text still counts as an answer.
  final String? recipeId;

  Map<String, dynamic> toJson() => <String, dynamic>{
    'text': text,
    'recipe_id': recipeId,
  };
}

/// How often a main protein should appear, e.g. fish twice a week. Either bound may be absent.
class ProteinTarget {
  const ProteinTarget({
    required this.protein,
    this.minPerWeek,
    this.maxPerWeek,
  });

  factory ProteinTarget.fromJson(Map<String, dynamic> json) => ProteinTarget(
    protein: _text(json['protein'])!,
    minPerWeek: _int(json['min_per_week']),
    maxPerWeek: _int(json['max_per_week']),
  );

  /// The corpus main-protein value, e.g. `fish`. Kept as a string: the app does not own that vocabulary.
  final String protein;
  final int? minPerWeek;
  final int? maxPerWeek;

  Map<String, dynamic> toJson() => <String, dynamic>{
    'protein': protein,
    'min_per_week': minPerWeek,
    'max_per_week': maxPerWeek,
  };
}

/// One line of the profile's running memory: what was learned, when, and from where.
class ProfileNote {
  const ProfileNote({
    required this.date,
    required this.text,
    required this.source,
  });

  factory ProfileNote.fromJson(Map<String, dynamic> json) => ProfileNote(
    date: _text(json['date'])!,
    text: _text(json['text'])!,
    source: ProfileNoteSource.values.firstWhere(
      (ProfileNoteSource value) => value.name == json['source'],
      orElse: () => ProfileNoteSource.interview,
    ),
  );

  /// `YYYY-MM-DD`, as the contract states it.
  final String date;
  final String text;
  final ProfileNoteSource source;

  Map<String, dynamic> toJson() => <String, dynamic>{
    'date': date,
    'text': text,
    'source': source.name,
  };
}

class HouseholdProfile {
  const HouseholdProfile({
    this.version = currentVersion,
    this.favouriteMeals = const <FavouriteMeal>[],
    this.lovedIngredients = const <String>[],
    this.dislikedIngredients = const <String>[],
    this.cuisinesLiked = const <String>[],
    this.cuisinesAvoided = const <String>[],
    this.proteinTargets = const <ProteinTarget>[],
    this.spiceTolerance,
    this.habits = '',
    this.household = '',
    this.notes = const <ProfileNote>[],
    this.interviewedAt,
  });

  /// Reads a profile from the contract's JSON. Never throws: see the library comment.
  factory HouseholdProfile.fromJson(
    Map<String, dynamic> json,
  ) => HouseholdProfile(
    version: _int(json['version']) ?? currentVersion,
    favouriteMeals: _objects(json['favourite_meals'], FavouriteMeal.fromJson),
    lovedIngredients: _strings(json['loved_ingredients']),
    dislikedIngredients: _strings(json['disliked_ingredients']),
    cuisinesLiked: _strings(json['cuisines_liked']),
    cuisinesAvoided: _strings(json['cuisines_avoided']),
    proteinTargets: _objects(json['protein_targets'], ProteinTarget.fromJson),
    spiceTolerance: SpiceTolerance.values
        .where((SpiceTolerance value) => value.name == json['spice_tolerance'])
        .firstOrNull,
    habits: _text(json['habits']) ?? '',
    household: _text(json['household']) ?? '',
    notes: _objects(json['notes'], ProfileNote.fromJson),
    interviewedAt: switch (json['interviewed_at']) {
      final String value => DateTime.tryParse(value)?.toUtc(),
      _ => null,
    },
  );

  /// A profile straight from a stored column or a response body, or `null` when [json] is not one.
  static HouseholdProfile? decode(String json) {
    try {
      final Object? decoded = jsonDecode(json);
      return decoded is Map<String, dynamic>
          ? HouseholdProfile.fromJson(decoded)
          : null;
    } on FormatException {
      return null;
    }
  }

  /// The version this build writes. A document read from elsewhere keeps its own.
  static const int currentVersion = 1;

  final int version;
  final List<FavouriteMeal> favouriteMeals;
  final List<String> lovedIngredients;

  /// A hard exclusion when the planner asks the corpus for eligible recipes.
  final List<String> dislikedIngredients;
  final List<String> cuisinesLiked;
  final List<String> cuisinesAvoided;
  final List<ProteinTarget> proteinTargets;
  final SpiceTolerance? spiceTolerance;

  /// Free text: how they plan and cook now.
  final String habits;

  /// Free text: who eats, kids, guests.
  final String household;
  final List<ProfileNote> notes;
  final DateTime? interviewedAt;

  Map<String, dynamic> toJson() => <String, dynamic>{
    'version': version,
    'favourite_meals': <Map<String, dynamic>>[
      for (final FavouriteMeal meal in favouriteMeals) meal.toJson(),
    ],
    'loved_ingredients': lovedIngredients,
    'disliked_ingredients': dislikedIngredients,
    'cuisines_liked': cuisinesLiked,
    'cuisines_avoided': cuisinesAvoided,
    'protein_targets': <Map<String, dynamic>>[
      for (final ProteinTarget target in proteinTargets) target.toJson(),
    ],
    'spice_tolerance': spiceTolerance?.name,
    'habits': habits,
    'household': household,
    'notes': <Map<String, dynamic>>[
      for (final ProfileNote note in notes) note.toJson(),
    ],
    'interviewed_at': interviewedAt?.toUtc().toIso8601String(),
  };

  String encode() => jsonEncode(toJson());
}

String? _text(Object? value) => switch (value) {
  final String text when text.trim().isNotEmpty => text.trim(),
  _ => null,
};

int? _int(Object? value) => switch (value) {
  final int number => number,
  final num number => number.toInt(),
  _ => null,
};

List<String> _strings(Object? value) => <String>[
  if (value is List)
    for (final Object? entry in value)
      if (_text(entry) case final String text) text,
];

/// Decodes a list of objects, skipping anything that is not one or that lacks a field its type requires.
List<T> _objects<T>(Object? value, T Function(Map<String, dynamic>) fromJson) {
  if (value is! List) return <T>[];
  final List<T> items = <T>[];
  for (final Object? entry in value) {
    if (entry is! Map<String, dynamic>) continue;
    try {
      items.add(fromJson(entry));
    } on TypeError {
      // A required field is missing or null: that one entry is unusable, the rest is not.
      continue;
    }
  }
  return items;
}
