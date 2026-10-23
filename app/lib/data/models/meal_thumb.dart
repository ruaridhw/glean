// The household's verdict on a meal they cooked: one of the two thumbs.

/// A thumb, named apart from drift's `MealRating` row class (generated from the `meal_ratings` table).
/// Declaration order is display order: up first, as the row draws them.
enum MealThumb {
  up('up'),
  down('down');

  const MealThumb(this.dbValue);

  /// Stored as TEXT in `meal_ratings.rating`.
  final String dbValue;

  /// Deliberately fail-fast, like `StoreSection.fromDb`: an unknown value is corrupt or newer-schema data
  /// and must surface rather than silently become one of the thumbs.
  static MealThumb fromDb(String value) => values.firstWhere(
    (thumb) => thumb.dbValue == value,
    orElse: () => throw StateError('Unknown meal thumb "$value"'),
  );

  /// The opposite thumb, for the row's tap: tapping the other one switches the rating to it.
  MealThumb get other => this == up ? down : up;
}
