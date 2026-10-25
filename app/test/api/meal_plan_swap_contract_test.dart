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
  test('a swap message is the type, the slot and the note', () {
    expect(
      const MealPlanSwapMessage(slot: 'rec_a', note: 'maybe fish').toJson(),
      <String, dynamic>{'type': 'swap', 'slot': 'rec_a', 'note': 'maybe fish'},
    );
    expect(const MealPlanSwapMessage(slot: 'rec_a').toJson()['note'], isNull);
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
          jsonEncode(<String, dynamic>{'session_id': 's 1', 'swap_id': 3}),
          202,
        );
      }),
      accessTokenProvider: () async => 'token',
    );

    final MealPlanSwapAccepted accepted = await client.sendMealPlanSwap(
      's 1',
      const MealPlanSwapMessage(slot: 'rec_a', note: 'fish'),
    );

    expect(sent.method, 'POST');
    expect(sent.url.path, '/meal-plan/sessions/s%201/messages');
    expect(jsonDecode(sent.body), <String, dynamic>{
      'type': 'swap',
      'slot': 'rec_a',
      'note': 'fish',
    });
    expect(accepted.swapId, 3);
  });
}
