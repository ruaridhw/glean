CREATE TABLE `ingredient_categories` (
	`category` text PRIMARY KEY NOT NULL,
	`food_group` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `ingredients` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`canonical_name` text NOT NULL,
	`api_ingredient_id` text,
	`api_name` text,
	`category` text,
	`canonical_unit` text,
	`is_staple` integer DEFAULT false NOT NULL,
	FOREIGN KEY (`category`) REFERENCES `ingredient_categories`(`category`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `ingredients_canonical_name_unique` ON `ingredients` (`canonical_name`);--> statement-breakpoint
CREATE TABLE `meal_plan_entries` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`recipe_id` integer NOT NULL,
	`planned_date` text NOT NULL,
	`cooked_at` text,
	`servings` integer DEFAULT 1 NOT NULL,
	FOREIGN KEY (`recipe_id`) REFERENCES `recipes`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `pantry_items` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`ingredient_id` integer NOT NULL,
	`quantity` real NOT NULL,
	`unit` text NOT NULL,
	`unit_price` real,
	`expiry_date` text,
	`last_used_at` text,
	`updated_at` text DEFAULT (datetime('now')) NOT NULL,
	FOREIGN KEY (`ingredient_id`) REFERENCES `ingredients`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `recipe_dietary_flags` (
	`recipe_id` integer NOT NULL,
	`flag` text NOT NULL,
	PRIMARY KEY(`recipe_id`, `flag`),
	FOREIGN KEY (`recipe_id`) REFERENCES `recipes`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE TABLE `recipe_ingredients` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`recipe_id` integer NOT NULL,
	`ingredient_id` integer NOT NULL,
	`quantity` real NOT NULL,
	`unit` text NOT NULL,
	`preparation` text,
	`is_optional` integer DEFAULT false NOT NULL,
	`substitutions` text DEFAULT '[]' NOT NULL,
	FOREIGN KEY (`recipe_id`) REFERENCES `recipes`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`ingredient_id`) REFERENCES `ingredients`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `recipes` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`external_id` text,
	`title` text NOT NULL,
	`source_url` text,
	`cuisine` text,
	`difficulty` text,
	`active_time_mins` integer,
	`total_time_mins` integer,
	`not_suitable_for` text DEFAULT '[]' NOT NULL,
	`yield_count` integer,
	`nutrition` text,
	`instructions` text DEFAULT '[]' NOT NULL,
	`last_cooked_at` text,
	`is_ai_generated` integer DEFAULT false NOT NULL
);
--> statement-breakpoint
CREATE TABLE `shopping_list_items` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`ingredient_id` integer,
	`name` text NOT NULL,
	`quantity` real,
	`unit` text,
	`source` text DEFAULT 'manual' NOT NULL,
	`is_checked` integer DEFAULT false NOT NULL,
	FOREIGN KEY (`ingredient_id`) REFERENCES `ingredients`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `user_config` (
	`id` integer PRIMARY KEY NOT NULL,
	`purchase_tolerance` real DEFAULT 0.5 NOT NULL,
	`preferred_servings` integer DEFAULT 2 NOT NULL,
	`meals_per_week` integer DEFAULT 5 NOT NULL,
	`dietary_flags` text DEFAULT '[]' NOT NULL,
	`max_active_time_mins` integer
);
