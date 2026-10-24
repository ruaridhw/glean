// The household's verdict on a meal they cooked: one of the two thumbs, and the note it can carry.

import 'package:characters/characters.dart';

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

/// The longest rating note the backend accepts (its `MAX_COOKED_NOTE_LENGTH`).
///
/// The bound counts **Unicode code points**, the unit Pydantic counts, so a note saved here can never fail
/// the next Generate request. Flutter's `TextField.maxLength` counts grapheme clusters instead, which a
/// combining sequence or a joined emoji makes smaller than the code-point count, so the note sheet counts
/// with [ratingNoteLength] rather than relying on `maxLength`.
const int maxRatingNoteLength = 500;

/// The length of [note] in code points: what the wire bound measures.
int ratingNoteLength(String note) => note.runes.length;

/// [note] cut to at most [limit] code points, never splitting a visible character.
///
/// A pasted comment can be longer than the field allows. Cutting on a code-point count alone could leave a
/// combining mark or half a joined emoji behind, so whole grapheme clusters are kept until the next one
/// would cross the bound.
String truncateRatingNote(String note, {int limit = maxRatingNoteLength}) {
  if (ratingNoteLength(note) <= limit) return note;
  final StringBuffer kept = StringBuffer();
  var used = 0;
  for (final String cluster in note.characters) {
    final int size = cluster.runes.length;
    if (used + size > limit) break;
    kept.write(cluster);
    used += size;
  }
  return kept.toString();
}
