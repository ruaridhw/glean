// Ported faithfully from the Expo app's `src/normalization/units.ts` (see
// git history). Keep aligned with the backend's recipe-import unit parsing
// (backend/src/glean/recipes/ingredient_parser.py) — recipe imports and
// meal-plan pantry math must agree on canonical units.
//
// Used by the pantry/plan repositories wherever a quantity needs converting
// into an ingredient's canonical/pantry unit (adding stock, decrementing on
// "Cooked").

/// Deterministic lookup: source unit -> conversion factor and target unit.
const Map<String, ({double factor, String to})> _unitConversions = {
  // Volume -> ml
  'l': (factor: 1000, to: 'ml'),
  'litre': (factor: 1000, to: 'ml'),
  'litres': (factor: 1000, to: 'ml'),
  'liter': (factor: 1000, to: 'ml'),
  'liters': (factor: 1000, to: 'ml'),
  'tsp': (factor: 4.92892, to: 'ml'),
  'teaspoon': (factor: 4.92892, to: 'ml'),
  'teaspoons': (factor: 4.92892, to: 'ml'),
  'tbsp': (factor: 14.7868, to: 'ml'),
  'tablespoon': (factor: 14.7868, to: 'ml'),
  'tablespoons': (factor: 14.7868, to: 'ml'),
  'fl oz': (factor: 29.5735, to: 'ml'),
  'cup': (factor: 236.588, to: 'ml'),
  'cups': (factor: 236.588, to: 'ml'),
  'pint': (factor: 473.176, to: 'ml'),
  'pints': (factor: 473.176, to: 'ml'),
  // Mass -> g
  'kg': (factor: 1000, to: 'g'),
  'kilogram': (factor: 1000, to: 'g'),
  'kilograms': (factor: 1000, to: 'g'),
  'oz': (factor: 28.3495, to: 'g'),
  'ounce': (factor: 28.3495, to: 'g'),
  'ounces': (factor: 28.3495, to: 'g'),
  'lb': (factor: 453.592, to: 'g'),
  'lbs': (factor: 453.592, to: 'g'),
  'pound': (factor: 453.592, to: 'g'),
  'pounds': (factor: 453.592, to: 'g'),
};

/// Density table (g per ml) for volume -> mass conversions when an
/// ingredient's canonical unit is 'g'.
const Map<String, double> _ingredientDensity = {
  'plain flour': 0.593,
  'bread flour': 0.593,
  'self-raising flour': 0.593,
  'caster sugar': 0.845,
  'granulated sugar': 0.845,
  'icing sugar': 0.561,
  'brown sugar': 0.845,
  'cocoa powder': 0.469,
  'baking soda': 1.08,
  'baking powder': 0.9,
  'rice': 0.888,
  'oats': 0.41,
  'rolled oats': 0.41,
  'honey': 1.42,
  'maple syrup': 1.32,
  'milk': 1.03,
  'cream': 1.01,
  'water': 1.0,
};

enum NormalizeSource { identity, lookup, density }

class NormalizeResult {
  const NormalizeResult({
    required this.quantity,
    required this.unit,
    required this.source,
  });

  final double quantity;
  final String unit;
  final NormalizeSource source;
}

/// Converts `quantity`/`unit` into `canonicalUnit`, using the density table
/// for volume<->mass conversions keyed by `canonicalName`. Returns null when
/// no conversion path exists (caller falls back to the raw quantity/unit).
NormalizeResult? normalizeUnit({
  required double quantity,
  required String unit,
  required String? canonicalUnit,
  required String canonicalName,
}) {
  final normalizedUnit = unit.toLowerCase().trim();

  if (canonicalUnit == null || normalizedUnit == canonicalUnit) {
    return NormalizeResult(
      quantity: quantity,
      unit: canonicalUnit ?? normalizedUnit,
      source: NormalizeSource.identity,
    );
  }

  final conv = _unitConversions[normalizedUnit];
  if (conv != null) {
    if (conv.to == canonicalUnit) {
      return NormalizeResult(
        quantity: quantity * conv.factor,
        unit: canonicalUnit,
        source: NormalizeSource.lookup,
      );
    }
    if (conv.to == 'ml' && canonicalUnit == 'g') {
      final density = _ingredientDensity[canonicalName.toLowerCase()];
      if (density != null) {
        return NormalizeResult(
          quantity: quantity * conv.factor * density,
          unit: 'g',
          source: NormalizeSource.density,
        );
      }
    }
    if (conv.to == 'g' && canonicalUnit == 'ml') {
      final density = _ingredientDensity[canonicalName.toLowerCase()];
      if (density != null) {
        return NormalizeResult(
          quantity: (quantity * conv.factor) / density,
          unit: 'ml',
          source: NormalizeSource.density,
        );
      }
    }
  }

  return null;
}
