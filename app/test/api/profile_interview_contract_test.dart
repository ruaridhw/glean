// `POST /profile/interview` is the one call the taste interview makes: it sends the transcript so far and gets
// either the next question or the finished profile with its two-line summary. These tests pin the wire shapes
// from the contract, both directions, and the client that carries them.
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/api_client.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/api/models/profile.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';

class MockHttpClient extends Mock implements http.Client {}

const Map<String, dynamic> _questionJson = <String, dynamic>{
  'status': 'question',
  'question': <String, dynamic>{
    'id': 'openers.favourite_meals',
    'text': 'What are three dinners you would happily eat every fortnight?',
    'options': <dynamic>[],
    'field': 'favourite_meals',
    'skippable': true,
  },
  'turn': 1,
  'max_turns': 7,
  'dropped_answer': false,
};

const Map<String, dynamic> _doneJson = <String, dynamic>{
  'status': 'done',
  'profile': <String, dynamic>{
    'version': 1,
    'favourite_meals': <dynamic>[
      <String, dynamic>{'text': 'katsu curry', 'recipe_id': 'rec_1'},
    ],
    'loved_ingredients': <dynamic>['miso'],
    'disliked_ingredients': <dynamic>['mushrooms'],
    'cuisines_liked': <dynamic>[],
    'cuisines_avoided': <dynamic>[],
    'protein_targets': <dynamic>[
      <String, dynamic>{
        'protein': 'fish',
        'min_per_week': 2,
        'max_per_week': null,
      },
    ],
    'spice_tolerance': 'mild',
    'habits': 'Quick weeknights',
    'household': 'Two adults',
    'notes': <dynamic>[],
    'interviewed_at': '2026-10-24T10:15:00.000Z',
  },
  'summary':
      'Loves katsu curry, never mushrooms.\nQuick weeknights, two adults.',
  'dropped_answer': true,
};

void main() {
  group('responses', () {
    test('a question response carries the question, the turn and the cap', () {
      final InterviewResponse response = InterviewResponse.fromJson(
        _questionJson,
      );

      expect(response, isA<InterviewQuestionResponse>());
      final InterviewQuestionResponse question =
          response as InterviewQuestionResponse;
      expect(question.droppedAnswer, isFalse);
      expect(question.turn, 1);
      expect(question.maxTurns, 7);
      expect(question.question.id, 'openers.favourite_meals');
      expect(question.question.options, isEmpty);
      expect(question.question.field, 'favourite_meals');
      expect(question.question.knownField, ProfileField.favouriteMeals);
      expect(question.question.skippable, isTrue);
    });

    test('a done response carries the profile and the two-line summary', () {
      final InterviewResponse response = InterviewResponse.fromJson(_doneJson);

      final InterviewDone done = response as InterviewDone;
      expect(done.droppedAnswer, isTrue);
      expect(
        done.summary,
        'Loves katsu curry, never mushrooms.\nQuick weeknights, two adults.',
      );
      // The profile is the app's own typed model, not a second copy of it.
      expect(done.profile.favouriteMeals.single.recipeId, 'rec_1');
      expect(done.profile.spiceTolerance, SpiceTolerance.mild);
      expect(done.profile.proteinTargets.single.maxPerWeek, isNull);
      expect(done.profile.interviewedAt, DateTime.utc(2026, 10, 24, 10, 15));
    });

    test('an option question keeps its chips in the backend order', () {
      final InterviewResponse response = InterviewResponse.fromJson(
        <String, dynamic>{
          ..._questionJson,
          'question': <String, dynamic>{
            ..._questionJson['question']! as Map<String, dynamic>,
            'id': 'openers.habits',
            'field': 'habits',
            'options': <dynamic>[
              'Quick weeknights',
              'Batch cook at the weekend',
              'Leftovers',
              'One treat meal',
              'Guests often',
            ],
          },
        },
      );

      expect((response as InterviewQuestionResponse).question.options, <String>[
        'Quick weeknights',
        'Batch cook at the weekend',
        'Leftovers',
        'One treat meal',
        'Guests often',
      ]);
      expect(response.question.field, 'habits');
      expect(response.question.knownField, ProfileField.habits);
    });

    test('a field this build does not know is kept as the backend named it, so '
        'the transcript replays verbatim', () {
      final InterviewResponse response = InterviewResponse.fromJson(
        <String, dynamic>{
          ..._questionJson,
          'question': <String, dynamic>{
            ..._questionJson['question']! as Map<String, dynamic>,
            'field': 'food_rules',
            'extra': 'ignored',
          },
        },
      );

      final InterviewQuestion asked =
          (response as InterviewQuestionResponse).question;
      expect(asked.knownField, isNull, reason: 'this build has no such field');
      expect(
        asked.field,
        'food_rules',
        reason:
            'the backend requires a known field back, so the raw value is kept',
      );
      expect(asked.toJson()['field'], 'food_rules');

      expect(
        () => InterviewResponse.fromJson(<String, dynamic>{
          ..._doneJson,
          'status': 'paused',
        }),
        throwsA(isA<FormatException>()),
      );
    });
  });

  group('request', () {
    test(
      'encodes the transcript and the draft profile in the contract shape',
      () {
        final InterviewRequest request = InterviewRequest(
          transcript: <InterviewTurn>[
            InterviewTurn(
              question: InterviewQuestion.fromJson(
                _questionJson['question']! as Map<String, dynamic>,
              ),
              answer: const InterviewAnswer(text: 'katsu curry, fish pie, dal'),
            ),
            InterviewTurn(
              question: InterviewQuestion.fromJson(
                _questionJson['question']! as Map<String, dynamic>,
              ),
              answer: const InterviewAnswer(skipped: true),
            ),
          ],
          draftProfile: const HouseholdProfile(),
        );

        expect(request.toJson(), <String, dynamic>{
          'transcript': <dynamic>[
            <String, dynamic>{
              'question': _questionJson['question'],
              'answer': <String, dynamic>{
                'text': 'katsu curry, fish pie, dal',
                'options': <dynamic>[],
                'skipped': false,
              },
            },
            <String, dynamic>{
              'question': _questionJson['question'],
              'answer': <String, dynamic>{
                'text': null,
                'options': <dynamic>[],
                'skipped': true,
              },
            },
          ],
          'draft_profile': const HouseholdProfile().toJson(),
        });
      },
    );

    test('a replayed question sends its field back exactly, including one this '
        'build does not know', () {
      InterviewQuestion parsed(Object? field) =>
          InterviewQuestion.fromJson(<String, dynamic>{
            'id': 'followup.spice',
            'text': 'How spicy is too spicy?',
            'options': <dynamic>[],
            'field': field,
            'skippable': true,
          });

      final Map<String, dynamic> encoded = InterviewRequest(
        transcript: <InterviewTurn>[
          InterviewTurn(
            question: parsed('spice_level'),
            answer: const InterviewAnswer(text: 'medium'),
          ),
        ],
        draftProfile: const HouseholdProfile(),
      ).toJson();

      expect(
        ((encoded['transcript']! as List<dynamic>).single
            as Map<String, dynamic>)['question'],
        containsPair('field', 'spice_level'),
      );
      expect(parsed('habits').toJson()['field'], 'habits');
    });

    test('an options answer keeps its chips', () {
      expect(
        const InterviewAnswer(
          options: <String>['Quick weeknights', 'One treat meal'],
        ).toJson(),
        <String, dynamic>{
          'text': null,
          'options': <String>['Quick weeknights', 'One treat meal'],
          'skipped': false,
        },
      );
    });
  });

  group('client', () {
    late MockHttpClient httpClient;
    late GleanApiClient api;

    setUpAll(() {
      registerFallbackValue(Uri.parse('http://localhost:9999/'));
    });

    setUp(() {
      httpClient = MockHttpClient();
      api = GleanApiClient(
        baseUrl: 'http://localhost:9999',
        httpClient: httpClient,
        accessTokenProvider: () async => 'token-1',
      );
    });

    test('posts the transcript and decodes the next question', () async {
      when(
        () => httpClient.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer(
        (_) async => http.Response(
          jsonEncode(_questionJson),
          200,
          headers: const <String, String>{'content-type': 'application/json'},
        ),
      );

      final InterviewResponse response = await api.continueInterview(
        const InterviewRequest(
          transcript: <InterviewTurn>[],
          draftProfile: HouseholdProfile(),
        ),
      );

      expect((response as InterviewQuestionResponse).turn, 1);

      final List<dynamic> sent = verify(
        () => httpClient.post(
          captureAny(),
          headers: captureAny(named: 'headers'),
          body: captureAny(named: 'body'),
        ),
      ).captured;
      expect((sent[0] as Uri).path, '/profile/interview');
      expect(sent[1], <String, String>{
        'Authorization': 'Bearer token-1',
        'Content-Type': 'application/json',
      });
      final Map<String, dynamic> body =
          jsonDecode(sent[2] as String) as Map<String, dynamic>;
      expect(body['transcript'], isEmpty);
      expect((body['draft_profile']! as Map<String, dynamic>)['version'], 1);
    });

    test('a rejected request surfaces as the typed API error the screen '
        'turns into plain copy', () async {
      when(
        () => httpClient.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer((_) async => http.Response('', 429));

      expect(
        () => api.continueInterview(
          const InterviewRequest(
            transcript: <InterviewTurn>[],
            draftProfile: HouseholdProfile(),
          ),
        ),
        throwsA(isA<ApiRateLimitException>()),
      );
    });
  });
}
