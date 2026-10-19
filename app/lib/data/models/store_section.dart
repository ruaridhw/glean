// The fixed, supermarket-agnostic store sections a shopping row is grouped under, in the order they are shown
// (a walk round a UK supermarket), with *Other* as the fallback.
//
// Until the ingredient catalogue supplies group and form, [resolveStoreSection] derives a section from the
// ingredient's name and its ingredient group; a household's own move for an ingredient overrides it.

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

  /// Deliberately fail-fast, like `ShoppingSource.fromDb`: an unknown stored value is corrupt or newer-schema
  /// data and must surface rather than be coerced to a section.
  static StoreSection fromDb(String value) => values.firstWhere(
    (s) => s.dbValue == value,
    orElse: () => throw StateError('Unknown store section "$value"'),
  );
}

const Map<String, StoreSection> _sectionByGroup = <String, StoreSection>{
  'leafy_greens': StoreSection.fruitAndVeg,
  'cabbage_and_broccoli': StoreSection.fruitAndVeg,
  'onions_and_garlic': StoreSection.fruitAndVeg,
  'root_veg': StoreSection.fruitAndVeg,
  'tomatoes_peppers_and_aubergines': StoreSection.fruitAndVeg,
  'fruit': StoreSection.fruitAndVeg,
  'fresh_herbs': StoreSection.fruitAndVeg,
  'red_meat': StoreSection.meatAndFish,
  'poultry': StoreSection.meatAndFish,
  'fish_and_seafood': StoreSection.meatAndFish,
  'dairy': StoreSection.dairyEggsChilled,
  'eggs': StoreSection.dairyEggsChilled,
  'bread': StoreSection.bakery,
  'beans_and_pulses': StoreSection.pastaRiceGrains,
  'grains': StoreSection.pastaRiceGrains,
  'pasta_and_rice': StoreSection.pastaRiceGrains,
  'oils_and_fats': StoreSection.foodCupboard,
  'dried_herbs': StoreSection.foodCupboard,
  'spices': StoreSection.foodCupboard,
  'sauces_and_condiments': StoreSection.foodCupboard,
  'nuts_and_seeds': StoreSection.foodCupboard,
  'baking': StoreSection.baking,
  'snacks_and_treats': StoreSection.snacksAndTreats,
  'drinks': StoreSection.drinks,
  'household': StoreSection.household,
  'health_and_beauty': StoreSection.healthAndBeauty,
  'baby': StoreSection.babyAndToddler,
  'pet': StoreSection.pet,
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

/// The section for an ingredient called [name] with the optional [groupId] (an ingredient group id). A household's
/// own choice, [override], always wins. Otherwise the name outranks the group where it says more: "plain flour" is a
/// grain but shelved with Baking, and frozen peas are beans and pulses but live in Frozen. Where nothing places it,
/// [StoreSection.other].
StoreSection resolveStoreSection({
  required String name,
  String? groupId,
  StoreSection? override,
}) {
  if (override != null) return override;
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
  return _sectionByGroup[groupId] ?? StoreSection.other;
}
