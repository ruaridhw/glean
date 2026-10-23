// The session contract is additive: a newer backend sends reason kinds, one alternative per new slot, a week
// summary and alternatives for planned meals, and an older one sends none of it. Both must parse, and both must
// reach the proposal screen without inventing data.
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/api/models/meal_plan_session.dart';

void main() {
  test('an old result without the new fields parses with neutral defaults', () {
    final response = MealPlanResponse.fromJson(<String, dynamic>{
      'suggestions': <Map<String, dynamic>>[
        {'recipe_id': 4, 'title': 'Old stew', 'reason': 'Fits the week'},
      ],
    });

    expect(response.suggestions, hasLength(1));
    expect(response.suggestions.single.reasonKind, isNull);
    expect(response.suggestions.single.alternative, isNull);
    expect(response.weekSummary, '');
    expect(response.plannedAlternatives, isEmpty);
    expect(response.degraded, isFalse);
  });

  test('a new result parses the summary, planned alternatives and the '
      'alternative per slot', () {
    final response = MealPlanResponse.fromJson(<String, dynamic>{
      'suggestions': <Map<String, dynamic>>[
        {
          'external_id': 'rec_a',
          'title': 'Beans',
          'reason': 'Uses the spinach',
          'reason_kind': 'urgent_item',
          'alternative': {
            'external_id': 'rec_b',
            'title': 'Chickpea dal',
            'reason': 'Also meat-free',
            'reason_kind': 'balance',
          },
        },
      ],
      'week_summary': 'Four quick dinners.',
      'planned_alternatives': [
        {
          'external_id': 'rec_planned',
          'alternative': {
            'external_id': 'rec_other',
            'title': 'Other dinner',
            'reason': 'Same shape',
          },
        },
      ],
      'degraded': true,
    });

    final suggestion = response.suggestions.single;
    expect(response.weekSummary, 'Four quick dinners.');
    expect(suggestion.reasonKind, 'urgent_item');
    expect(suggestion.alternative!.title, 'Chickpea dal');
    expect(suggestion.alternative!.alternative, isNull);
    expect(response.plannedAlternatives.single.externalId, 'rec_planned');
    expect(
      response.plannedAlternatives.single.alternative.title,
      'Other dinner',
    );
    expect(response.degraded, isTrue);
  });

  test('cancelled is a known terminal status', () {
    final update = MealPlanSessionUpdate.fromJson(<String, dynamic>{
      'status': 'cancelled',
      'progress': <String>[],
      'next_cursor': 2,
    });

    expect(update.status, MealPlanSessionStatus.cancelled);
    expect(update.isTerminal, isTrue);
  });

  test('a status this build does not know stays non-terminal', () {
    final update = MealPlanSessionUpdate.fromJson(<String, dynamic>{
      'status': 'a_new_status',
    });

    expect(update.status, MealPlanSessionStatus.unknown);
    expect(update.isTerminal, isFalse);
  });
}
