# vulture_whitelist.py
# Names used by external frameworks that vulture cannot detect statically.

handler  # Mangum Lambda entry point, referenced by SAM template.yaml
application  # ASGI app consumed by Mangum handler
tracer  # AWS X-Ray PowerTools, used via @tracer.capture_lambda_handler
export_db  # FastAPI route handler, registered by @router.post()
health  # FastAPI route handler, registered by @router.get()
anthropic_api_key  # Pydantic Settings field
langchain_project  # Pydantic Settings field, read by LangSmith SDK via env var
validate_model  # called from integration tests (tests/ excluded from vulture scan)
get_default_model  # convenience factory for callers that need a default chat model
recipe_api_key  # Pydantic Settings field
recipe_api_base_url  # Pydantic Settings field
log_level  # Pydantic Settings field
rate_limit_per_hour  # Pydantic Settings field
model_config  # Pydantic v2 model configuration
_validate_iso_duration  # Pydantic field validator
name  # Pydantic field (ParsedIngredient, CompressedPantryItem)
quantity  # Pydantic field (ParsedIngredient, CompressedPantryItem)
unit  # Pydantic field (ParsedIngredient, CompressedPantryItem)
unit_price  # ParsedIngredient Pydantic field
confidence  # ParsedIngredient Pydantic field
# recipes/schemas.py Pydantic fields
api_ingredient_id  # RecipeIngredientOut field
canonical_name  # RecipeIngredientOut field
external_id  # RecipeOut / RecipeSearchResult field
title  # Pydantic field (RecipeOut, RecipeSearchResult, MealPlanRecipe)
dietary_flags  # RecipeOut / RecipeSearchResult field
# meal_plan schemas — fields accessed via Pydantic model_dump / FastAPI serialisation
id  # CompressedPantryItem
food_group  # CompressedPantryItem
urgency_score  # CompressedPantryItem
recipe_id  # RecipeHistoryItem / MealPlanRecipe
last_cooked_at  # RecipeHistoryItem
food_groups  # RecipeHistoryItem
reason  # MealPlanRecipe
missing_ingredients  # MealPlanRecipe
suggestions  # MealPlanResponse compatibility field
generate_meal_plan  # FastAPI route handler
parse_description  # FastAPI route handler
get_field_value  # PydanticBaseSettingsSource abstract method implementation
field  # PydanticBaseSettingsSource abstract method implementation argument
settings_customise_sources  # pydantic-settings hook, called by BaseSettings metaclass
cls  # classmethod first argument (settings_customise_sources)
ExceptionHandler  # Starlette exception handler type used only for static cast
clarifying_questions  # ShoppingParseResponse Pydantic field
_value_  # Enum internal attribute, set explicitly in Feature.__new__ to attach per-member policy
# nutrition.py NutritionFields — canonical Pydantic fields, moved between layers via model_dump()
calories  # NutritionFields
protein_g  # NutritionFields
carbohydrates_g  # NutritionFields
fat_g  # NutritionFields
fibre_g  # NutritionFields
sugar_g  # NutritionFields
sodium_mg  # NutritionFields
