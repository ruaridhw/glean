export const DIETARY_OPTIONS = [
  "Vegetarian",
  "Vegan",
  "Gluten-Free",
  "Dairy-Free",
  "Nut-Free",
  "Keto",
  "Paleo",
] as const;

interface IntegerRange {
  min: number;
  max: number;
}

export const SETTINGS_OPTION_RANGES = {
  // Dinners per week is a 3–7 slider in the redesign (chips are reserved for dietary flags).
  dinnersPerWeek: { min: 3, max: 7 },
  defaultServings: { min: 1, max: 6 },
  maxActiveTimeMins: { min: 1, max: 480 },
} as const satisfies Record<string, IntegerRange>;

export function buildIntegerOptions({ min, max }: IntegerRange): number[] {
  return Array.from({ length: max - min + 1 }, (_, index) => min + index);
}

export function getToleranceLabel(tolerance: number): string {
  if (tolerance <= 0.2) return "Strict: pantry ingredients only";
  if (tolerance <= 0.5) return "Moderate: minor shopping OK";
  return "Open: happy to buy new ingredients";
}

export function validateBoundedInteger(
  value: string,
  min: number,
  max: number,
  label: string,
): string | null {
  if (!value) return `${label} is required`;
  const parsed = parseInt(value, 10);
  if (Number.isNaN(parsed) || parsed < min || parsed > max) {
    return `${label} must be between ${min} and ${max}`;
  }
  return null;
}
