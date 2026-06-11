import type { Ionicons } from "@expo/vector-icons";
import type { Recipe, RecipeIngredient } from "@/types";

interface RecipeMetaItem {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
}

interface InstructionStep {
  number: number;
  text: string;
}

type RawInstruction = string | { step_number?: number; text?: string };
const COMPACT_UNITS = new Set(["g", "kg", "ml", "l", "tsp", "tbsp", "cm"]);

export function getRecipeMeta(recipe: Recipe): RecipeMetaItem[] {
  return [
    recipe.total_time_mins
      ? { icon: "time-outline", label: `${recipe.total_time_mins} min` }
      : null,
    recipe.yield_count ? { icon: "people-outline", label: `${recipe.yield_count} servings` } : null,
    recipe.difficulty ? { icon: "speedometer-outline", label: recipe.difficulty } : null,
  ].filter((item): item is RecipeMetaItem => item != null);
}

export function getRecipeTags(recipe: Recipe): string[] {
  return [recipe.cuisine, ...(recipe.dietary_flags ?? [])].filter((tag): tag is string =>
    Boolean(tag),
  );
}

export function formatRecipeIngredient(ingredient: RecipeIngredient): string {
  const name = ingredient.ingredient?.canonical_name ?? "";
  const preparation = ingredient.preparation ? `, ${ingredient.preparation}` : "";
  const optional = ingredient.is_optional ? " (optional)" : "";
  const quantity = formatQuantity(ingredient.quantity);
  if (!ingredient.quantity && !ingredient.unit) {
    return `${name}${preparation}${optional}`.trim();
  }
  if (ingredient.unit === "pcs") {
    return `${quantity}x ${name}${preparation}${optional}`.trim();
  }
  if (COMPACT_UNITS.has(ingredient.unit)) {
    return `${quantity}${ingredient.unit} ${name}${preparation}${optional}`.trim();
  }
  return `${quantity} ${ingredient.unit} ${name}${preparation}${optional}`.trim();
}

export function parseInstructionSteps(instructions: unknown): InstructionStep[] {
  const parsed =
    typeof instructions === "string"
      ? (JSON.parse(instructions) as RawInstruction[])
      : instructions;
  if (!Array.isArray(parsed)) return [];
  return parsed.map((step, index) => {
    if (typeof step === "string") return { number: index + 1, text: step };
    return { number: step.step_number ?? index + 1, text: step.text ?? "" };
  });
}

function formatQuantity(quantity: number): string {
  return Number.isInteger(quantity) ? quantity.toFixed(0) : `${quantity}`;
}
