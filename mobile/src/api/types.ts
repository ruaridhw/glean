// mobile/src/api/types.ts
// API response types — mirrors backend Pydantic schemas.

// --- Receipts ---

export interface ParsedIngredient {
  name: string;
  quantity: number;
  unit: string;
  unit_price: number | null;
  confidence: number;
}

export interface ScanResponse {
  items: ParsedIngredient[];
}

export interface DescribeResponse {
  items: ParsedIngredient[];
}

// --- Shopping ---

export interface ShoppingProposalItem extends ParsedIngredient {
  api_ingredient_id: string | null;
  category: string | null;
}

export interface ShoppingParseRequest {
  text: string;
}

export interface ShoppingParseResponse {
  items: ShoppingProposalItem[];
  clarifying_questions: string[];
}

// --- Recipes ---

export interface RecipeIngredientOut {
  api_ingredient_id: string | null;
  canonical_name: string;
  quantity: number;
  unit: string;
  preparation: string | null;
  is_optional: boolean;
  substitutions: string[];
}

export interface NutritionOut {
  calories: number;
  protein_g: number;
  carbohydrates_g: number;
  fat_g: number;
  fibre_g: number;
  sugar_g: number;
  sodium_mg: number;
}

export interface InstructionOut {
  step_number: number;
  phase: string;
  text: string;
}

export interface RecipeOut {
  external_id: string;
  title: string;
  source_url: string | null;
  cuisine: string | null;
  difficulty: string | null;
  active_time_mins: number | null;
  total_time_mins: number | null;
  dietary_flags: string[];
  not_suitable_for: string[];
  yield_count: number | null;
  nutrition: NutritionOut | null;
  instructions: InstructionOut[];
  ingredients: RecipeIngredientOut[];
}

export interface RecipeSearchResult {
  external_id: string;
  title: string;
  cuisine: string | null;
  difficulty: string | null;
  total_time_mins: number | null;
  dietary_flags: string[];
}

export interface RecipeSearchResponse {
  results: RecipeSearchResult[];
  total: number;
}

// --- Meal plan generation ---

// A planned meal: a saved recipe (recipe_id) or a corpus recipe (external_id).
export interface MealPlanSuggestion {
  recipe_id: number | null;
  external_id: string | null;
  title: string;
  reason: string;
}

export interface MealPlanResponse {
  suggestions: MealPlanSuggestion[];
}
