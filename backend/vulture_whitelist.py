# vulture_whitelist.py
# Names used by external frameworks that vulture cannot detect statically.

handler  # Mangum Lambda entry point, referenced by SAM template.yaml
application  # ASGI app consumed by Mangum handler
tracer  # AWS X-Ray PowerTools, used via @tracer.capture_lambda_handler
export_db  # FastAPI route handler, registered by @router.post()
list_backups  # FastAPI route handler, registered by @router.get()
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
_fallback_out_of_taxonomy_category  # Pydantic field validator (ParsedIngredient.category)
_fallback_out_of_catalogue_group  # Pydantic field validator (ParsedIngredient.ingredient_group)
_agree_category_and_group  # Pydantic model validator (ParsedIngredient)
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
# unit_backfill.py — used by scripts/backfill_recipe_units.py, outside vulture's src/ scan
backfill_unit_words  # one-off corpus backfill entry point
recipes_scanned  # UnitBackfillResult field
recipes_changed  # UnitBackfillResult field
ingredients_changed  # UnitBackfillResult field
# shopping/schemas.py ShoppingUnit members (mirror the app's shoppingUnits) and validator
G  # ShoppingUnit member
KG  # ShoppingUnit member
ML  # ShoppingUnit member
L  # ShoppingUnit member
UNITS  # ShoppingUnit member
PACK  # ShoppingUnit member
BOTTLE  # ShoppingUnit member
BAG  # ShoppingUnit member
BOX  # ShoppingUnit member
_drop_unit_price  # Pydantic field validator (ShoppingProposalItem.unit_price)
# catalogue/: the store contract is consumed by normalisation (#123) and the DynamoDB store (#130), not yet in src
CatalogueStore
InMemoryCatalogueStore
shortlist
upsert_alias
create_provisional
record_unmatched
is_unmatched
density_g_per_ml  # CatalogueItem Pydantic field
_trim_aliases  # Pydantic field validator
_check_form_and_stock_unit  # Pydantic model validator
section  # CatalogueItem resolved rule
SEED  # Source enum member
load_seed  # seed loader, consumed by the DynamoDB store loader (#130)
version  # SeedData Pydantic field
unmatched_names
DynamoCatalogueStore  # used by scripts/seed_catalogue.py and, from #123, the normalisation path
seed  # DynamoCatalogueStore.seed, called by scripts/seed_catalogue.py
counts_towards_balance  # FoodGroup property, consumed by the meal plan

# TODO: the first consuming PRs (#125's dietary check, #123's normalisation) must remove the
# decisions.py entries below as they start using each name.
# decisions.py: public API, first used by #125 (dietary check) and #123 (normalisation)
true  # NoulCriteria field, set by keyword in dietary_decisions.py
false  # NoulCriteria field, as above
probabilities  # ChoiceAnswer / ScoreAnswer field
score  # ScoreAnswer field, and Decision.score accessor
input_tokens  # Usage field
output_tokens  # Usage field
cost  # Usage field
provider  # Decision field
usage  # Decision field
__cause__  # exception chain cleared in DecisionClient.decide so upstream text can't leak via causes
__context__  # as above
produce_missing_decisions  # used by scripts/compute_dietary_decisions.py
render  # CoverageReport.render, printed by scripts/enrich_corpus.py and make enrich-corpus
failures  # CoverageReport field, asserted in tests and read by operators in the report

# catalogue/normalise.py: NormalisedName response fields and the route handler are read by FastAPI / the app
catalogue_item_id  # NormalisedName field
ingredient_group  # NormalisedName field
normalise_names  # POST /catalogue/normalise route

# catalogue/router.py: sync response fields and the route handler are read by FastAPI / the app
groups  # CatalogueSyncResponse field
sync_catalogue  # GET /catalogue route

# recipes/ (F1/#162): the corpus behind one backend seam
_from_legacy_flag  # Pydantic model validator (RecipeAnswer, pre-F1 dietary JSONL lines)

# recipes/enrichment/ (F2/#163): enrichers declare questions, the runner asks and stores them
HIGH  # SafeSide.HIGH: declared now so V5's attribute questions state their safe side, per ADR 0025
