// V10's swap contract: the message the app sends to `POST /meal-plan/sessions/{id}/messages`, the 202 it gets
// back, and the `swap` a poll carries. A backend without swaps sends no `swap`, and a newer one may send a state
// or note this build does not know; both must parse without inventing an outcome.
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/api_client.dart';
import 'package:glean/api/models/meal_plan_session.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('each message is its type and its fields, as one union', () {
    expect(
      const SwapMessage(
        slot: 'rec_a',
        week: <String>['rec_a', 'rec_b'],
        note: 'maybe fish',
      ).toJson(),
      <String, dynamic>{
        'type': 'swap',
        'slot': 'rec_a',
        'note': 'maybe fish',
        'week': <String>['rec_a', 'rec_b'],
      },
    );
    expect(
      const SwapMessage(
        slot: 'rec_a',
        week: <String>['rec_a'],
      ).toJson()['note'],
      isNull,
    );
    // An answer leaves out what it does not carry; the backend reads a missing field as null.
    expect(const AnswerMessage(option: 'Fish').toJson(), <String, dynamic>{
      'type': 'answer',
      'option': 'Fish',
    });
    expect(const SkipMessage().toJson(), <String, dynamic>{'type': 'skip'});
  });

  test('the 202 carries the swap id and whether the note was dropped', () {
    final swap = MealPlanMessageAccepted.fromJson(<String, dynamic>{
      'session_id': 's1',
      'swap_id': 2,
      'note_dropped': true,
    });
    expect(swap.swapId, 2);
    expect(swap.noteDropped, isTrue);
    final answer = MealPlanMessageAccepted.fromJson(<String, dynamic>{
      'session_id': 's1',
      'swap_id': null,
      'note_dropped': false,
    });
    expect(answer.swapId, isNull);
    expect(answer.noteDropped, isFalse);
  });

  test(
    'a poll carries the newest swap, with the replacement once it is done',
    () {
      final update = MealPlanSessionUpdate.fromJson(<String, dynamic>{
        'status': 'done',
        'progress': <String>['Reading your note', 'Checking it fits the week'],
        'next_cursor': 7,
        'swap': <String, dynamic>{
          'swap_id': 2,
          'slot': 'rec_a',
          'position': 1,
          'state': 'done',
          'note': 'dropped',
          'replacement': <String, dynamic>{
            'external_id': 'rec_fish',
            'title': 'Prawn linguine',
            'reason': 'Lighter, as you asked.',
          },
        },
      });

      final MealPlanSessionSwap swap = update.swap!;
      expect(swap.swapId, 2);
      expect(swap.position, 1);
      expect(swap.state, MealPlanSwapState.done);
      expect(swap.note, MealPlanSwapNote.dropped);
      expect(swap.replacement!.title, 'Prawn linguine');
    },
  );

  test('no swap, and states this build does not know, parse safely', () {
    expect(
      MealPlanSessionUpdate.fromJson(<String, dynamic>{'status': 'done'}).swap,
      isNull,
    );
    final swap = MealPlanSessionSwap.fromJson(<String, dynamic>{
      'swap_id': 1,
      'slot': 'rec_a',
      'position': 0,
      'state': 'something_new',
      'note': 'something_else',
    });
    expect(swap.state, MealPlanSwapState.unknown);
    expect(swap.note, MealPlanSwapNote.unknown);
    expect(swap.replacement, isNull);
  });

  test('the client posts the swap to the session messages route', () async {
    late http.Request sent;
    final client = GleanApiClient(
      baseUrl: 'https://api.test',
      httpClient: MockClient((http.Request request) async {
        sent = request;
        return http.Response(
          jsonEncode(<String, dynamic>{
            'session_id': 's 1',
            'swap_id': 3,
            'note_dropped': false,
          }),
          202,
        );
      }),
      accessTokenProvider: () async => 'token',
    );

    final MealPlanMessageAccepted accepted = await client
        .sendMealPlanSessionMessage(
          's 1',
          const SwapMessage(
            slot: 'rec_a',
            week: <String>['rec_a'],
            note: 'fish',
          ),
        );

    expect(sent.method, 'POST');
    expect(sent.url.path, '/meal-plan/sessions/s%201/messages');
    expect(jsonDecode(sent.body), <String, dynamic>{
      'type': 'swap',
      'slot': 'rec_a',
      'note': 'fish',
      'week': <String>['rec_a'],
    });
    expect(accepted.swapId, 3);
  });
}
