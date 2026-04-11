// mobile/src/normalization/units.ts

// Deterministic lookup: source_unit → { factor to apply, target unit }
const UNIT_CONVERSIONS: Record<string, { factor: number; to: string }> = {
  // Volume → ml
  l: { factor: 1000, to: "ml" },
  litre: { factor: 1000, to: "ml" },
  litres: { factor: 1000, to: "ml" },
  liter: { factor: 1000, to: "ml" },
  liters: { factor: 1000, to: "ml" },
  tsp: { factor: 4.92892, to: "ml" },
  teaspoon: { factor: 4.92892, to: "ml" },
  teaspoons: { factor: 4.92892, to: "ml" },
  tbsp: { factor: 14.7868, to: "ml" },
  tablespoon: { factor: 14.7868, to: "ml" },
  tablespoons: { factor: 14.7868, to: "ml" },
  "fl oz": { factor: 29.5735, to: "ml" },
  cup: { factor: 236.588, to: "ml" },
  cups: { factor: 236.588, to: "ml" },
  pint: { factor: 473.176, to: "ml" },
  pints: { factor: 473.176, to: "ml" },
  // Mass → g
  kg: { factor: 1000, to: "g" },
  kilogram: { factor: 1000, to: "g" },
  kilograms: { factor: 1000, to: "g" },
  oz: { factor: 28.3495, to: "g" },
  ounce: { factor: 28.3495, to: "g" },
  ounces: { factor: 28.3495, to: "g" },
  lb: { factor: 453.592, to: "g" },
  lbs: { factor: 453.592, to: "g" },
  pound: { factor: 453.592, to: "g" },
  pounds: { factor: 453.592, to: "g" },
};

// Density table (g per ml) for volume→mass conversions when canonical_unit is 'g'.
const INGREDIENT_DENSITY: Record<string, number> = {
  "plain flour": 0.593,
  "bread flour": 0.593,
  "self-raising flour": 0.593,
  "caster sugar": 0.845,
  "granulated sugar": 0.845,
  "icing sugar": 0.561,
  "brown sugar": 0.845,
  "cocoa powder": 0.469,
  "baking soda": 1.08,
  "baking powder": 0.9,
  rice: 0.888,
  oats: 0.41,
  "rolled oats": 0.41,
  honey: 1.42,
  "maple syrup": 1.32,
  milk: 1.03,
  cream: 1.01,
  water: 1.0,
};

interface NormalizeResult {
  quantity: number;
  unit: string;
  source: "identity" | "lookup" | "density";
}

export function normalizeUnit(params: {
  quantity: number;
  unit: string;
  canonicalUnit: string | null;
  canonicalName: string;
}): NormalizeResult | null {
  const { quantity, canonicalUnit, canonicalName } = params;
  const unit = params.unit.toLowerCase().trim();

  if (!canonicalUnit || unit === canonicalUnit) {
    return { quantity, unit: canonicalUnit ?? unit, source: "identity" };
  }

  const conv = UNIT_CONVERSIONS[unit];
  if (conv) {
    if (conv.to === canonicalUnit) {
      return { quantity: quantity * conv.factor, unit: canonicalUnit, source: "lookup" };
    }
    if (conv.to === "ml" && canonicalUnit === "g") {
      const density = INGREDIENT_DENSITY[canonicalName.toLowerCase()];
      if (density !== undefined) {
        return { quantity: quantity * conv.factor * density, unit: "g", source: "density" };
      }
    }
    if (conv.to === "g" && canonicalUnit === "ml") {
      const density = INGREDIENT_DENSITY[canonicalName.toLowerCase()];
      if (density !== undefined) {
        return { quantity: (quantity * conv.factor) / density, unit: "ml", source: "density" };
      }
    }
  }

  return null;
}
