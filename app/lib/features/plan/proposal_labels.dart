/// The badges a proposal card shows for a meal: main protein, main carb, dish type and hands-on time.
///
/// The values are the backend's G1 vocabulary (spec 6.1, "Attribute values"); the words are the app's own short
/// display labels, kept in one place so the card never renders a raw enum. Two rules:
///
/// - **Unknown is absent.** A value the backend did not send is one the decision model was not confident about
///   (it stored `unsure`) or has not measured yet, so no badge is invented for it.
/// - **"None" is not a badge.** "No protein" or "no carb" is a fact about the recipe, not something to label a
///   meal with; the card shows the protein or carbohydrate it does have, or nothing.
///
/// Order matches V3's design (direction A, `design-gates/v3-v8-wireframes.html`): protein · carb · dish · time,
/// as in "fish · rice · traybake · 20 min".
library;

import 'package:glean/api/models/meal_plan.dart';

/// Short display words for the G1 protein values.
const Map<String, String> _proteinLabels = <String, String>{
  'chicken': 'chicken',
  'turkey_or_duck': 'turkey or duck',
  'beef': 'beef',
  'pork': 'pork',
  'lamb': 'lamb',
  'fish': 'fish',
  'seafood': 'seafood',
  'beans_and_pulses': 'beans',
  'tofu_or_plant_protein': 'plant protein',
  'vegetarian_other': 'veg',
  'mixed': 'mixed protein',
};

/// Short display words for the G1 carb values.
const Map<String, String> _carbLabels = <String, String>{
  'rice': 'rice',
  'pasta': 'pasta',
  'noodles': 'noodles',
  'potato': 'potato',
  'bread_or_wraps': 'wraps',
  'other_grains': 'grains',
};

/// Short display words for the G1 dish types.
const Map<String, String> _dishLabels = <String, String>{
  'curry': 'curry',
  'stir_fry': 'stir-fry',
  'pasta_dish': 'pasta',
  'soup_or_stew': 'stew',
  'roast_or_traybake': 'traybake',
  'salad_or_bowl': 'salad',
  'handheld': 'handheld',
  'pie_or_bake': 'pie',
  'rice_dish': 'rice dish',
  'pan_or_grill': 'grilled',
};

/// The badges for one meal, in the order the card shows them. Empty when nothing is known.
List<String> proposalLabels(MealPlanAttributes? attributes) {
  if (attributes == null) {
    return const <String>[];
  }
  final String? protein = _proteinLabels[attributes.mainProtein];
  final String? carb = _carbLabels[attributes.mainCarb];
  final String? dish = _dishLabels[attributes.dishType];
  final int? minutes = attributes.activeTimeMins;
  return <String>[
    ?protein,
    ?carb,
    ?dish,
    ?(minutes == null ? null : '${minutes.clamp(1, 999)} min'),
  ];
}
