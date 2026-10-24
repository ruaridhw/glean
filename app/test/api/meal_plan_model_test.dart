import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/models/meal_plan.dart';

Map<String, dynamic> _suggestion({List<dynamic>? usesUp}) => <String, dynamic>{
  'recipe_id': null,
  'external_id': 'rec_herby',
  'title': 'Coriander Chicken',
  'reason': 'Uses up your coriander (goes off Thu).',
  'uses_up': ?usesUp,
};

void main() {
  test('parses the pantry items a meal uses up, with their days', () {
    final recipe = MealPlanRecipe.fromJson(
      _suggestion(
        usesUp: [
          {'name': 'coriander', 'expires_in_days': 2, 'goes_off': 'Thu'},
          {'name': 'limes', 'expires_in_days': 5, 'goes_off': null},
        ],
      ),
    );

    expect(recipe.usesUp, hasLength(2));
    expect(recipe.usesUp.first.name, 'coriander');
    expect(recipe.usesUp.first.expiresInDays, 2);
    expect(recipe.usesUp.first.goesOff, 'Thu');
    expect(recipe.usesUp.last.name, 'limes');
    expect(recipe.usesUp.last.goesOff, isNull);
  });

  test('has no used-up items when the server sends none', () {
    final recipe = MealPlanRecipe.fromJson(_suggestion());

    expect(recipe.usesUp, isEmpty);
  });
}
