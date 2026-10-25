import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/features/plan/proposal_labels.dart';

/// The badge row a proposal card shows: protein · carb · dish · time (V3 direction A).
///
/// These are the wire's G1 values turned into the app's short words. The card never renders a raw enum, never
/// invents a value the backend left out, and shows no "none" as a badge.
void main() {
  group('proposalLabels', () {
    test('orders the badges protein, carb, dish, then hands-on time', () {
      const MealPlanAttributes attributes = MealPlanAttributes(
        mainProtein: 'fish',
        mainCarb: 'potato',
        dishType: 'roast_or_traybake',
        activeTimeMins: 20,
      );

      expect(proposalLabels(attributes), <String>[
        'fish',
        'potato',
        'traybake',
        '20 min',
      ]);
    });

    test('labels every G1 protein, carb and dish type with a word', () {
      const Map<String, List<String>> expected = <String, List<String>>{
        'chicken': <String>['chicken'],
        'turkey_or_duck': <String>['turkey or duck'],
        'beef': <String>['beef'],
        'pork': <String>['pork'],
        'lamb': <String>['lamb'],
        'fish': <String>['fish'],
        'seafood': <String>['seafood'],
        'beans_and_pulses': <String>['beans'],
        'tofu_or_plant_protein': <String>['plant protein'],
        'vegetarian_other': <String>['veg'],
        'mixed': <String>['mixed protein'],
        'rice': <String>['rice'],
        'pasta': <String>['pasta'],
        'noodles': <String>['noodles'],
        'potato': <String>['potato'],
        'bread_or_wraps': <String>['wraps'],
        'other_grains': <String>['grains'],
        'curry': <String>['curry'],
        'stir_fry': <String>['stir-fry'],
        'pasta_dish': <String>['pasta'],
        'soup_or_stew': <String>['stew'],
        'roast_or_traybake': <String>['traybake'],
        'salad_or_bowl': <String>['salad'],
        'handheld': <String>['handheld'],
        'pie_or_bake': <String>['pie'],
        'rice_dish': <String>['rice dish'],
        'pan_or_grill': <String>['grilled'],
      };
      for (final MapEntry<String, List<String>> entry in expected.entries) {
        final List<String> labels =
            proposalLabels(MealPlanAttributes(mainProtein: entry.key)) +
            proposalLabels(MealPlanAttributes(mainCarb: entry.key)) +
            proposalLabels(MealPlanAttributes(dishType: entry.key));
        expect(
          labels,
          contains(entry.value.single),
          reason: '${entry.key} must have a display label',
        );
      }
    });

    test('no protein, no carb and the unshown dish type produce no badge', () {
      const MealPlanAttributes attributes = MealPlanAttributes(
        mainProtein: 'none',
        mainCarb: 'none',
        dishType: 'other',
      );

      expect(proposalLabels(attributes), isEmpty);
    });

    test('an unknown value from a newer backend produces no badge either', () {
      const MealPlanAttributes attributes = MealPlanAttributes(
        mainProtein: 'reptile',
        activeTimeMins: 25,
      );

      expect(proposalLabels(attributes), <String>['25 min']);
    });

    test(
      'a meal an older backend sent, or one not measured yet, has no badges',
      () {
        expect(
          proposalLabels(null),
          isEmpty,
          reason: 'the field is absent entirely',
        );
        expect(proposalLabels(const MealPlanAttributes()), isEmpty);
      },
    );

    test('the time badge is the minutes the backend resolved', () {
      expect(
        proposalLabels(const MealPlanAttributes(activeTimeMins: 15)),
        <String>['15 min'],
      );
      expect(
        proposalLabels(const MealPlanAttributes(activeTimeMins: 1)),
        <String>['1 min'],
      );
    });
  });
}
