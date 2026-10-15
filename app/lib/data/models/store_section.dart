// The fixed, supermarket-agnostic store sections a shopping row is grouped under, in the order they are shown
// (a walk round a UK supermarket), with *Other* as the fallback.
//
// Until the ingredient catalogue supplies group and form, [resolveStoreSection] derives a section from the
// ingredient's name and its category (one of today's 23); a household's own move for an ingredient overrides it.

/// A store section. Declaration order is display order, with [other] last.
enum StoreSection {
  fruitAndVeg('fruit_and_veg', 'Fruit & Veg'),
  meatAndFish('meat_and_fish', 'Meat & Fish'),
  dairyEggsChilled('dairy_eggs_chilled', 'Dairy, Eggs & Chilled'),
  bakery('bakery', 'Bakery'),
  frozen('frozen', 'Frozen'),
  pastaRiceGrains('pasta_rice_grains', 'Pasta, Rice & Grains'),
  foodCupboard('food_cupboard', 'Food Cupboard'),
  baking('baking', 'Baking'),
  snacksAndTreats('snacks_and_treats', 'Snacks & Treats'),
  drinks('drinks', 'Drinks'),
  household('household', 'Household'),
  healthAndBeauty('health_and_beauty', 'Health & Beauty'),
  babyAndToddler('baby_and_toddler', 'Baby & Toddler'),
  pet('pet', 'Pet'),
  other('other', 'Other');

  const StoreSection(this.dbValue, this.label);

  /// Stored as TEXT in `ingredients.store_section`.
  final String dbValue;
  final String label;
}

const Map<String, StoreSection> _sectionByCategory = <String, StoreSection>{
  'leafy_greens': StoreSection.fruitAndVeg,
  'brassicas': StoreSection.fruitAndVeg,
  'alliums': StoreSection.fruitAndVeg,
  'root_vegetables': StoreSection.fruitAndVeg,
  'nightshades': StoreSection.fruitAndVeg,
  'citrus': StoreSection.fruitAndVeg,
  'tropical_fruit': StoreSection.fruitAndVeg,
  'stone_fruit': StoreSection.fruitAndVeg,
  'berries': StoreSection.fruitAndVeg,
  'herbs_fresh': StoreSection.fruitAndVeg,
  'red_meat': StoreSection.meatAndFish,
  'poultry': StoreSection.meatAndFish,
  'seafood': StoreSection.meatAndFish,
  'dairy': StoreSection.dairyEggsChilled,
  'eggs': StoreSection.dairyEggsChilled,
  'bread': StoreSection.bakery,
  'legumes': StoreSection.pastaRiceGrains,
  'grains': StoreSection.pastaRiceGrains,
  'pasta_rice': StoreSection.pastaRiceGrains,
  'oils_fats': StoreSection.foodCupboard,
  'herbs_dried': StoreSection.foodCupboard,
  'spices': StoreSection.foodCupboard,
  'condiments': StoreSection.foodCupboard,
};

const Set<String> _bakingLastWords = <String>{'flour', 'sugar'};
const List<String> _bakingPhrases = <String>[
  'baking powder',
  'baking soda',
  'bicarbonate',
  'cocoa',
  'yeast',
];
const Set<String> _foodCupboardWords = <String>{
  'oil',
  'oils',
  'vinegar',
  'stock',
  'bouillon',
};

/// The section for an ingredient called [name] with the optional [category] (a key of the 23-category
/// taxonomy). The name outranks the category where it says more: "plain flour" is a grain by category but
/// shelved with Baking, and frozen peas are legumes by category but live in Frozen. Where nothing places it,
/// [StoreSection.other].
StoreSection resolveStoreSection({required String name, String? category}) {
  final String lower = name.toLowerCase();
  final List<String> words = lower
      .split(RegExp(r'[^a-z]+'))
      .where((String w) => w.isNotEmpty)
      .toList();
  if (words.contains('frozen')) return StoreSection.frozen;
  // Flour and sugar only as the thing itself ("caster sugar"), never "sugar snap peas".
  if (words.isNotEmpty && _bakingLastWords.contains(words.last)) {
    return StoreSection.baking;
  }
  if (_bakingPhrases.any(lower.contains)) return StoreSection.baking;
  if (words.any(_foodCupboardWords.contains)) return StoreSection.foodCupboard;
  return _sectionByCategory[category] ?? StoreSection.other;
}
