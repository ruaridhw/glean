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
cooked_at  # CookedHistoryItem
cooked_history  # MealPlanRequest
rating  # CookedHistoryItem field (the household's thumb), read via model_dump / serialisation
note  # CookedHistoryItem field, part of the request contract only
latest_rating  # EligibleRecipes field the scorer's thumbs-up term will read
_read_a_missing_offset_as_utc  # Pydantic field validator (CookedHistoryItem.cooked_at)
reason  # MealPlanRecipe
missing_ingredients  # MealPlanRecipe
uses_up  # MealPlanSuggestion field the app renders later
reason_kind  # MealPlanSuggestion field the app renders later
alternative  # MealPlanSuggestion field the app renders later
PROFILE  # ReasonKind member: the evidence V13's profile will cite (the app parses every member)
FEEDBACK  # ReasonKind member: the evidence V9's chips will cite (the app parses every member)
HISTORY  # ReasonKind member: the evidence the cooked history cites (the app parses every member)
ANSWER  # ReasonKind member: the evidence an interview answer cites (the app parses every member)
goes_off  # UsedUpPantryItem field the app renders later
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
render  # CoverageReport.render, printed by scripts/enrich_corpus.py and make enrich-corpus
failures  # CoverageReport field, asserted in tests and read by operators in the report

# catalogue/normalise.py: NormalisedName response fields and the route handler are read by FastAPI / the app
catalogue_item_id  # NormalisedName field
ingredient_group  # NormalisedName field
normalise_names  # POST /catalogue/normalise route

# catalogue/router.py: sync response fields and the route handler are read by FastAPI / the app
groups  # CatalogueSyncResponse field
sync_catalogue  # GET /catalogue route

# agent sessions: the async stack's entry points, and the fields the app reads off a poll
handler  # glean.worker.handler, referenced by template.yaml
dlq_handler  # glean.worker.dlq_handler, referenced by template.yaml
create_session  # FastAPI route handler (POST /meal-plan/sessions)
get_session  # FastAPI route handler (GET /meal-plan/sessions/{id})
cancel_session  # FastAPI route handler (DELETE /meal-plan/sessions/{id})
post_session_message  # FastAPI route handler (POST /meal-plan/sessions/{id}/messages)
WAITING_FOR_USER  # SessionStatus member: the app's contract, written once the agent can ask a question (V11)
CANCELLED  # SessionStatus member: the app's contract once DELETE /meal-plan/sessions/{id} exists (V3)
retry_after_minutes  # SessionError field, read by the app
created_at  # SessionRecord field, kept for the table's own audit trail
_plan_from_the_corpus  # Pydantic field validator (SessionRequest.source)
_says_something  # Pydantic model validator (AnswerMessage: an option or a note)
writes  # InMemorySessionStore counter, asserted in tests that polling never writes
# sessions/store.py: the queue and worker numbers template.yaml must declare, and the lease arithmetic
# between them; all of them are asserted in tests/infra/test_template_async_stack.py.
QUEUE_VISIBILITY_SECONDS
WORKER_TIMEOUT_SECONDS
LAMBDA_INIT_SECONDS
QUEUE_VISIBILITY_MARGIN_SECONDS
MAX_LEASE_SECONDS
DEAD_LETTER_VISIBILITY_SECONDS  # the dead-letter queue's retry cadence, asserted in the template test

# dietary model substitution: the calibration and evaluation are read by scripts, tests and the eval CLI,
# which vulture does not scan (it scans src/ only).
evidence  # DietaryCalibration field: provenance read when a calibration is reviewed
TREE_NUT_FREE_THRESHOLD  # convenience alias read by tests/meal_plan/test_dietary_decisions.py
PEANUT_FREE_THRESHOLD  # as above
PREFERENCE_THRESHOLD  # read by the audit script and tests
THRESHOLDS  # read by scripts/audit_dietary_corpus.py and tests
load_labelled_samples  # used by scripts/evaluate_dietary_model.py and the live sample test
evaluate_dietary_model  # used by scripts/evaluate_dietary_model.py and the live sample test
# recipes/ (F1/#162): the corpus behind one backend seam
_from_legacy_flag  # Pydantic model validator (RecipeAnswer, pre-F1 dietary JSONL lines)

# recipes/enrichment/ (F2): enrichers declare questions, the runner asks and stores them
HIGH  # SafeSide.HIGH: declared now so V5's attribute questions state their safe side, per ADR 0025


# The G1 attribute contract's enum members are read by value (a projection entry, a question's criteria, a
# label) and the questions key their criteria on the members, so no member needs a line here. What is left is
# a Pydantic validator, which only Pydantic calls.
_labelled_questions_carry_a_value  # Pydantic model validator (RecipeAnswer: a labelled answer must carry a value)

# meal_plan/tools.py (V6): the scorer's contract, read by the agent graph (V7), the evals (6.6) and the tests
MAIN_PROTEIN  # PredicateField member: a chip names the attribute it filters on (V9)
MAIN_CARB  # PredicateField member, as above
DISH_TYPE  # PredicateField member, as above
CUISINE  # PredicateField member, as above
NOT_IN  # PredicateOp member, from the spec's filter shape; V9's chips write it
detail  # PlanPenalty field: the value, median or target the penalty is about
within_15_percent  # PlanGap: the eval's within-15% gate, read by the evals (6.6) and V7

# agent/graph.py (V7): PlanState keys LangGraph merges into the checkpointed state; nodes read them with .get()
invalid_actions  # PlanState key: answers that did not parse as a NextAction, counted for the session metrics
degraded_reason  # PlanState key: why finalise wrote the scorer's week, logged with the session metrics

# screening.py (the injection screen, ported unchanged from the taste interview)
clear_screen_cache  # screening.py, called by the tests to start from a cold cache

# meal_plan/schemas.py (V9): the week feedback
_each_chip_once  # Pydantic field validator (HumanFeedback.chips)
_ignore_unknown_chips  # Pydantic field validator (HumanFeedback.chips)
feedback_note  # MealPlanResult field, read by the app
# agent/graph.py (V10): the swap's PlanState keys, merged into the checkpointed state and read with .get()
swap_note  # PlanState key: the swap note the injection screen passed, the only form a model ever reads
swap_pick  # PlanState key: the replacement the model proposed, before swap_finalise validates it
swap_outcome  # PlanState key: the swap's finished outcome, keyed by swap id so a crash republishes it
note_dropped  # MessageAccepted field: the 202 tells the app the screen dropped the note ("Couldn't use that note")
questions_asked  # PlanState key (V11): how many questions the agent has asked, at most one
working_seconds  # PlanState key (V11): the working time spent before the question, carried into the resume

# profile/schemas.py: the household profile and the interview contract, read by FastAPI, the app and the model
# MainProtein members: the settled attribute vocabulary (spec §6.1), not all used in src yet
interview  # POST /profile/interview route handler
CHICKEN  # MainProtein member
TURKEY_OR_DUCK  # MainProtein member
BEEF  # MainProtein member
PORK  # MainProtein member
LAMB  # MainProtein member
FISH  # MainProtein member
SEAFOOD  # MainProtein member
TOFU_OR_PLANT_PROTEIN  # MainProtein member
VEGETARIAN_OTHER  # MainProtein member
MIXED  # MainProtein member
PROTEIN_TARGETS  # ProfileField member, targeted by a model-chosen follow-up
NOTES  # ProfileField member, targeted by a model-chosen follow-up
INTERVIEW  # NoteSource member, appended from the interview
FEEDBACK  # NoteSource member, the proposal screen's notes (V15)
protein  # ProteinTarget field
_bounds_are_ordered  # Pydantic model validator (ProteinTarget)
interviewed_at  # HouseholdProfile field, stamped by the service
skippable  # InterviewQuestion field, always true
max_turns  # InterviewQuestionResponse field
dropped_answer  # InterviewQuestionResponse / InterviewDoneResponse field
clear_screen_cache  # screening.py, called by the tests to start from a cold cache
WRITABLE_PROFILE_FIELDS  # schemas.py, the fields an interview question may target
WritableProfileField  # schemas.py, the narrowed field enum the model schema uses
_answers_belong_to_this_interview  # Pydantic model validator (InterviewRequest)
question_for_turn  # schemas.py, the server's own question for a turn number
