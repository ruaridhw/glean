export const DIETARY_OPTIONS = [
  "Vegetarian",
  "Vegan",
  "Gluten-Free",
  "Dairy-Free",
  "Nut-Free",
  "Keto",
  "Paleo",
] as const;

export const SERVINGS_OPTIONS = [1, 2, 3, 4, 6] as const;
export const DINNERS_OPTIONS = [3, 4, 5, 6, 7] as const;

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
