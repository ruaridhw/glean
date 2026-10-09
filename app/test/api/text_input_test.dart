// Port of the Expo app's src/__tests__/normalization/text-input.test.ts
// (see git history) — per the
// API module brief, this trim/validate wrapper was the only logic in the RN
// `api/hooks.ts` its own tests actually exercised.
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/text_input.dart';

void main() {
  group('normalizeSubmittedText', () {
    test(
      'trims outer whitespace while preserving intentional multiline spacing',
      () {
        expect(
          normalizeSubmittedText(' \n  milk\n  sourdough bread  \n\t'),
          'milk\n  sourdough bread',
        );
      },
    );
  });

  group('toRequiredSubmittedText', () {
    test('returns null for values that are empty after trimming', () {
      expect(toRequiredSubmittedText(' \n\t  '), isNull);
    });

    test('returns the trimmed value when non-empty', () {
      expect(toRequiredSubmittedText('  eggs  '), 'eggs');
    });
  });

  group('requireSubmittedText', () {
    test('throws EmptyTextInputException for blank input', () {
      expect(
        () => requireSubmittedText('   '),
        throwsA(isA<EmptyTextInputException>()),
      );
    });

    test('returns the trimmed value when non-empty', () {
      expect(requireSubmittedText(' bread '), 'bread');
    });
  });
}
