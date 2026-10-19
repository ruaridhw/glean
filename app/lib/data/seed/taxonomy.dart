// Seed data: the 10 staples, and how the 23 categories an older backend (or an older database) still names map onto
// ingredient groups. The groups themselves are in `ingredient_groups.dart`.

/// The ingredient group each of the 23 old categories became. Fruit was four categories. A category or a null that
/// isn't here maps to [otherGroupId]; no row is ever dropped.
const Map<String, String> legacyCategoryGroups = <String, String>{
  'leafy_greens': 'leafy_greens',
  'brassicas': 'cabbage_and_broccoli',
  'alliums': 'onions_and_garlic',
  'root_vegetables': 'root_veg',
  'nightshades': 'tomatoes_peppers_and_aubergines',
  'legumes': 'beans_and_pulses',
  'citrus': 'fruit',
  'tropical_fruit': 'fruit',
  'stone_fruit': 'fruit',
  'berries': 'fruit',
  'red_meat': 'red_meat',
  'poultry': 'poultry',
  'seafood': 'fish_and_seafood',
  'eggs': 'eggs',
  'dairy': 'dairy',
  'grains': 'grains',
  'pasta_rice': 'pasta_and_rice',
  'bread': 'bread',
  'oils_fats': 'oils_and_fats',
  'herbs_fresh': 'fresh_herbs',
  'herbs_dried': 'dried_herbs',
  'spices': 'spices',
  'condiments': 'sauces_and_condiments',
};

const String otherGroupId = 'other';

/// The group an older backend response's [category] names, or null for none, which the caller reads as unclassified.
String? groupForLegacyCategory(String? category) =>
    category == null ? null : legacyCategoryGroups[category];

/// A staple ingredient seeded with `isStaple = true` so pantry logic that
/// treats staples specially (e.g. shopping shortfalls) has real data from
/// first launch.
class StapleSeed {
  const StapleSeed(this.canonicalName, this.groupId);

  final String canonicalName;
  final String groupId;
}

const List<StapleSeed> stapleSeeds = [
  StapleSeed('olive oil', 'oils_and_fats'),
  StapleSeed('salt', 'spices'),
  StapleSeed('black pepper', 'spices'),
  StapleSeed('garlic', 'onions_and_garlic'),
  StapleSeed('onion', 'onions_and_garlic'),
  StapleSeed('butter', 'dairy'),
  StapleSeed('eggs', 'eggs'),
  StapleSeed('plain flour', 'grains'),
  StapleSeed('sugar', 'sauces_and_condiments'),
  StapleSeed('tomato paste', 'sauces_and_condiments'),
];
