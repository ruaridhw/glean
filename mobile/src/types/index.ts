// mobile/src/types/index.ts

export interface IngredientCategory {
  category: string;
  food_group: string;
}

export interface Ingredient {
  id: number;
  canonical_name: string;
  api_ingredient_id?: string | null;
  api_name?: string | null;
  category?: string | null;
  canonical_unit?: string | null;
  is_staple: boolean;
}

export interface PantryItem {
  id: number;
  ingredient_id: number;
  quantity: number;
  unit: string;
  unit_price?: number | null;
  expiry_date?: string | null;
  last_used_at?: string | null;
  updated_at: string;
  // Joined fields (populated at query time)
  canonical_name: string;
  is_staple: boolean;
  food_group?: string | null;
}

export interface RecipeDietaryFlag {
  recipe_id: number;
  flag: string;
}

export interface Recipe {
  id: number;
  external_id?: string | null;
  title: string;
  source_url?: string | null;
  cuisine?: string | null;
  difficulty?: string | null;
  active_time_mins?: number | null;
  total_time_mins?: number | null;
  not_suitable_for: string[]; // JSON array, serialised as text in DB
  yield_count?: number | null;
  nutrition?: string | null; // JSON string
  instructions: string[]; // JSON array, serialised as text in DB
  last_cooked_at?: string | null;
  is_ai_generated: boolean;
  // Populated at query time from recipe_dietary_flags join
  dietary_flags?: string[];
}

export interface RecipeIngredient {
  id: number;
  recipe_id: number;
  ingredient_id: number;
  quantity: number;
  unit: string;
  preparation?: string | null;
  is_optional: boolean;
  substitutions: string[]; // JSON array, serialised as text in DB
  // Joined field
  ingredient?: Ingredient;
}

export interface MealPlanEntry {
  id: number;
  recipe_id: number;
  planned_date: string; // ISO date string YYYY-MM-DD
  cooked_at?: string | null;
  servings: number;
  // Joined field
  recipe?: Recipe;
}

export interface ShoppingListItem {
  id: number;
  ingredient_id?: number | null;
  name: string;
  quantity?: number | null;
  unit?: string | null;
  source: "manual" | "meal_plan" | "ai";
  is_checked: boolean;
}

export interface UserConfig {
  id: number;
  purchase_tolerance: number;
  preferred_servings: number;
  meals_per_week: number;
  dietary_flags: string[]; // JSON array, serialised as text in DB
  max_active_time_mins?: number | null;
}
