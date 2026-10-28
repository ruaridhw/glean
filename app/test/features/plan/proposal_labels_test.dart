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
        'about 20 min',
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

      expect(proposalLabels(attributes), <String>['about 25 min']);
    });

    test('a badge never repeats a word already in the row', () {
      // A pasta dish's carb and its dish type both said "pasta" before this rule; 6 of the 50 sample
      // recipes are pasta dishes, so it showed up often.
      expect(
        proposalLabels(
          const MealPlanAttributes(mainCarb: 'pasta', dishType: 'pasta_dish'),
        ),
        <String>['pasta'],
      );
      // The same overlap for rice, where the dish badge would add only the word "dish".
      expect(
        proposalLabels(
          const MealPlanAttributes(mainCarb: 'rice', dishType: 'rice_dish'),
        ),
        <String>['rice'],
      );
      // A badge that shares no word is kept: wraps and handheld describe different things.
      expect(
        proposalLabels(
          const MealPlanAttributes(
            mainCarb: 'bread_or_wraps',
            dishType: 'handheld',
          ),
        ),
        <String>['wraps', 'handheld'],
      );
      // Dropping one badge never drops the time.
      expect(
        proposalLabels(
          const MealPlanAttributes(
            mainCarb: 'pasta',
            dishType: 'pasta_dish',
            activeTimeMins: 25,
          ),
        ),
        <String>['pasta', 'about 25 min'],
      );
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
        <String>['about 15 min'],
      );
      expect(
        proposalLabels(const MealPlanAttributes(activeTimeMins: 1)),
        <String>['about 1 min'],
      );
    });
  });
}
