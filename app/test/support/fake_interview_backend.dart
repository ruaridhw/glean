// A scripted `POST /profile/interview` for widget tests. Not a test suite itself (no `_test.dart` suffix).
//
// The interview is one paid call per turn, so a test scripts exactly the turns it cares about and can then
// read back every body the app sent: which answer was given, which was skipped, and whether the transcript
// was replayed faithfully.
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';

class MockHttpClient extends Mock implements http.Client {}

/// Registers the fallback [Uri] mocktail needs for `any()` on the request URI.
void registerInterviewFallbacks() {
  registerFallbackValue(Uri.parse('http://localhost:9999/profile/interview'));
}

/// One scripted response: a JSON body, or a bare status code for a failure.
typedef ScriptedResponse = Object;

Map<String, dynamic> questionResponse({
  required int turn,
  String id = 'openers.habits',
  String text = 'How do your weeks usually go?',
  List<String> options = const <String>[],
  String field = 'habits',
  int maxTurns = 7,
  bool droppedAnswer = false,
}) => <String, dynamic>{
  'status': 'question',
  'question': <String, dynamic>{
    'id': id,
    'text': text,
    'options': options,
    'field': field,
    'skippable': true,
  },
  'turn': turn,
  'max_turns': maxTurns,
  'dropped_answer': droppedAnswer,
};

Map<String, dynamic> doneResponse({
  String summary =
      'Loves katsu curry, never mushrooms.\nQuick weeknights, two adults.',
  bool droppedAnswer = false,
  Map<String, dynamic>? profile,
}) => <String, dynamic>{
  'status': 'done',
  'profile':
      profile ??
      <String, dynamic>{
        'version': 1,
        'favourite_meals': <dynamic>[
          <String, dynamic>{'text': 'katsu curry', 'recipe_id': 'rec_1'},
        ],
        'loved_ingredients': <dynamic>['miso'],
        'disliked_ingredients': <dynamic>['mushrooms'],
        'cuisines_liked': <dynamic>[],
        'cuisines_avoided': <dynamic>[],
        'protein_targets': <dynamic>[],
        'spice_tolerance': 'mild',
        'habits': 'Quick weeknights',
        'household': 'Two adults',
        'notes': <dynamic>[],
        'interviewed_at': '2026-10-24T10:15:00.000Z',
      },
  'summary': summary,
  'dropped_answer': droppedAnswer,
};

class FakeInterviewBackend {
  FakeInterviewBackend(List<ScriptedResponse> script)
    : _script = List<ScriptedResponse>.of(script);

  /// The bodies the app posted, in order: `{"transcript": [...], "draft_profile": {...}}`.
  final List<Map<String, dynamic>> requests = <Map<String, dynamic>>[];

  final List<ScriptedResponse> _script;
  late final MockHttpClient client = MockHttpClient();

  bool _attached = false;

  /// The transcript of the last request, as the app sent it.
  List<dynamic> get lastTranscript =>
      (requests.last['transcript']! as List<dynamic>);

  /// The last answer the app sent.
  Map<String, dynamic> get lastAnswer =>
      (lastTranscript.last as Map<String, dynamic>)['answer']!
          as Map<String, dynamic>;

  void attach() {
    if (_attached) return;
    _attached = true;
    when(
      () => client.post(
        any(),
        headers: any(named: 'headers'),
        body: any(named: 'body'),
      ),
    ).thenAnswer((Invocation invocation) async {
      requests.add(
        jsonDecode(invocation.namedArguments[#body]! as String)
            as Map<String, dynamic>,
      );
      // An exhausted script repeats its last response, so a test that only cares about the first turn does
      // not have to script the whole interview.
      final ScriptedResponse next = _script.length > 1
          ? _script.removeAt(0)
          : _script.single;
      return switch (next) {
        final int status => http.Response('', status),
        final Map<String, dynamic> body => http.Response(
          jsonEncode(body),
          200,
          headers: const <String, String>{'content-type': 'application/json'},
        ),
        final Object other => throw StateError(
          'unsupported scripted response: $other',
        ),
      };
    });
  }
}
