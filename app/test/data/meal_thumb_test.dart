// The note bound is one rule shared with the backend: it counts Unicode code points, not the grapheme
// clusters Flutter's TextField counts, so a note saved here always passes the backend's validation.
import 'package:characters/characters.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/meal_thumb.dart';

void main() {
  test(
    'a combining sequence counts its code points, not its visible characters',
    () {
      expect(ratingNoteLength('e\u0301'), 2);
      expect(ratingNoteLength('e\u0301' * 300), 600);
    },
  );

  test('a joined emoji counts every code point it is built from', () {
    // One family, one visible glyph, five code points.
    const String family = '\u{1F468}\u200D\u{1F469}\u200D\u{1F467}';
    expect(family.characters.length, 1);
    expect(ratingNoteLength(family), 5);
  });

  test('a note within the bound is left exactly as it is', () {
    const String note = 'too sweet for the kids';

    expect(truncateRatingNote(note), note);
  });

  test(
    'an over-long note is cut to the bound without splitting a character',
    () {
      final String over = 'e\u0301' * 300;

      final String cut = truncateRatingNote(over);

      expect(ratingNoteLength(cut), lessThanOrEqualTo(maxRatingNoteLength));
      expect(
        cut.characters.every((String cluster) => cluster == 'e\u0301'),
        isTrue,
      );
    },
  );

  test(
    'an emoji that would cross the bound is dropped whole rather than halved',
    () {
      // 499 ASCII characters leave room for one code point, not for a 5-code-point family.
      final String note =
          '${'a' * (maxRatingNoteLength - 1)}'
          '\u{1F468}\u200D\u{1F469}\u200D\u{1F467}';

      final String cut = truncateRatingNote(note);

      expect(ratingNoteLength(cut), lessThanOrEqualTo(maxRatingNoteLength));
      expect(cut, 'a' * (maxRatingNoteLength - 1));
    },
  );
}
