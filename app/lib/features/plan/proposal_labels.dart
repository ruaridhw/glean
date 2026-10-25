/// The badges a proposal card shows for a meal: main protein, main carb, dish type and hands-on time.
///
/// The values are the backend's G1 vocabulary (spec 6.1, "Attribute values"); the words are the app's own short
/// display labels, kept in one place so the card never renders a raw enum. Two rules:
///
/// - **Unknown is absent.** A value the backend did not send is one the decision model was not confident about
///   (it stored `unsure`) or has not measured yet, so no badge is invented for it.
/// - **"None" is not a badge.** "No protein" or "no carb" is a fact about the recipe, not something to label a
///   meal with; the card shows the protein or carbohydrate it does have, or nothing.
/// - **The time is approximate in words.** The number is the active-time bucket's upper bound, capped by the
///   recipe's total time, or the total time alone when no bucket was measured — so it can be either a "up to
///   30 minutes" estimate or a stated total. The card has one string for both, and "about N min" is honest for
///   both; a second format would need a source flag on the wire.
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
///
/// `pasta_dish` is not "pasta": a pasta dish's card already says "pasta" for its carb, and two identical
/// badges read like a mistake (6 of the 50 sample recipes are pasta dishes). It keeps the shape instead,
/// which is what the dish badge is for.
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
///
/// A badge whose words are already in the row is left out: a pasta carb and a pasta dish would otherwise show
/// "pasta · pasta", and a rice dish reads "rice · rice dish". The carb comes first, so the more specific dish
/// badge is the one that goes; the row never repeats a word.
List<String> proposalLabels(MealPlanAttributes? attributes) {
  if (attributes == null) {
    return const <String>[];
  }
  final int? minutes = attributes.activeTimeMins;
  final List<String?> candidates = <String?>[
    _proteinLabels[attributes.mainProtein],
    _carbLabels[attributes.mainCarb],
    _dishLabels[attributes.dishType],
    minutes == null ? null : 'about ${minutes.clamp(1, 999)} min',
  ];
  final List<String> labels = <String>[];
  final Set<String> words = <String>{};
  for (final String? label in candidates) {
    if (label == null) {
      continue;
    }
    final Set<String> labelWords = label.split(' ').toSet();
    if (labelWords.any(words.contains)) {
      continue; // the row already says this word
    }
    labels.add(label);
    words.addAll(labelWords);
  }
  return labels;
}
