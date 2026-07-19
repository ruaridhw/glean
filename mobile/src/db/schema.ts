// mobile/src/db/schema.ts

import { sql } from "drizzle-orm";
import { integer, primaryKey, real, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const ingredientCategories = sqliteTable("ingredient_categories", {
  category: text("category").primaryKey(),
  food_group: text("food_group").notNull(),
});

export const ingredients = sqliteTable("ingredients", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  canonical_name: text("canonical_name").unique().notNull(),
  api_ingredient_id: text("api_ingredient_id"),
  api_name: text("api_name"),
  category: text("category").references(() => ingredientCategories.category),
  canonical_unit: text("canonical_unit"),
  is_staple: integer("is_staple", { mode: "boolean" }).notNull().default(false),
});

export const pantryItems = sqliteTable("pantry_items", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  ingredient_id: integer("ingredient_id")
    .notNull()
    .references(() => ingredients.id),
  quantity: real("quantity").notNull(),
  unit: text("unit").notNull(),
  unit_price: real("unit_price"),
  expiry_date: text("expiry_date"),
  last_used_at: text("last_used_at"),
  updated_at: text("updated_at").notNull().default(sql`(datetime('now'))`),
});

export const recipes = sqliteTable("recipes", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  external_id: text("external_id"),
  title: text("title").notNull(),
  source_url: text("source_url"),
  cuisine: text("cuisine"),
  difficulty: text("difficulty"),
  active_time_mins: integer("active_time_mins"),
  total_time_mins: integer("total_time_mins"),
  not_suitable_for: text("not_suitable_for").notNull().default("[]"),
  yield_count: integer("yield_count"),
  nutrition: text("nutrition"),
  instructions: text("instructions").notNull().default("[]"),
  last_cooked_at: text("last_cooked_at"),
});

export const recipeDietaryFlags = sqliteTable(
  "recipe_dietary_flags",
  {
    recipe_id: integer("recipe_id")
      .notNull()
      .references(() => recipes.id, { onDelete: "cascade" }),
    flag: text("flag").notNull(),
  },
  (table) => ({
    pk: primaryKey({ columns: [table.recipe_id, table.flag] }),
  }),
);

export const recipeIngredients = sqliteTable("recipe_ingredients", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  recipe_id: integer("recipe_id")
    .notNull()
    .references(() => recipes.id, { onDelete: "cascade" }),
  ingredient_id: integer("ingredient_id")
    .notNull()
    .references(() => ingredients.id),
  quantity: real("quantity").notNull(),
  unit: text("unit").notNull(),
  preparation: text("preparation"),
  is_optional: integer("is_optional", { mode: "boolean" }).notNull().default(false),
  substitutions: text("substitutions").notNull().default("[]"),
});

export const mealPlanEntries = sqliteTable("meal_plan_entries", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  recipe_id: integer("recipe_id")
    .notNull()
    .references(() => recipes.id),
  planned_date: text("planned_date").notNull(),
  cooked_at: text("cooked_at"),
  servings: integer("servings").notNull().default(1),
});

export const shoppingListItems = sqliteTable("shopping_list_items", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  ingredient_id: integer("ingredient_id").references(() => ingredients.id),
  name: text("name").notNull(),
  quantity: real("quantity"),
  unit: text("unit"),
  source: text("source").notNull().default("manual"),
  is_checked: integer("is_checked", { mode: "boolean" }).notNull().default(false),
});

// Single source of truth for user-config defaults, shared by the column defaults below and
// by the "no row yet" fallback in db/config.ts so the two can't drift.
export const USER_CONFIG_DEFAULTS = {
  purchase_tolerance: 0.5,
  preferred_servings: 2,
  meals_per_week: 5,
  dietary_flags: [] as string[],
  max_active_time_mins: null as number | null,
};

export const userConfig = sqliteTable("user_config", {
  id: text("id").primaryKey(), // Cognito user sub (UUID)
  purchase_tolerance: real("purchase_tolerance")
    .notNull()
    .default(USER_CONFIG_DEFAULTS.purchase_tolerance),
  preferred_servings: integer("preferred_servings")
    .notNull()
    .default(USER_CONFIG_DEFAULTS.preferred_servings),
  meals_per_week: integer("meals_per_week").notNull().default(USER_CONFIG_DEFAULTS.meals_per_week),
  dietary_flags: text("dietary_flags")
    .notNull()
    .default(JSON.stringify(USER_CONFIG_DEFAULTS.dietary_flags)),
  max_active_time_mins: integer("max_active_time_mins"),
});
