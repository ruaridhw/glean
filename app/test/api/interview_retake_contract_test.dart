import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/models/profile.dart';

void main() {
  test('explicit clear cannot serialize alongside text, options or skip', () {
    for (final answer in <InterviewAnswer>[
      const InterviewAnswer(clear: true, text: ''),
      const InterviewAnswer(clear: true, options: <String>['Fish']),
      const InterviewAnswer(clear: true, skipped: true),
    ]) {
      expect(answer.toJson, throwsArgumentError);
    }
    expect(const InterviewAnswer(clear: true).toJson(), <String, dynamic>{
      'text': null,
      'options': <String>[],
      'skipped': false,
      'clear': true,
    });
  });

  test(
    'unknown or independent memory targets cannot be accepted as interview writes',
    () {
      for (final field in <String>['notes', 'dismissed_notes', 'surprise']) {
        expect(
          () => InterviewResponse.fromJson(<String, dynamic>{
            'status': 'done',
            'profile': <String, dynamic>{},
            'summary': '',
            'updated_fields': <String>[field],
          }),
          throwsFormatException,
        );
      }
    },
  );
}
