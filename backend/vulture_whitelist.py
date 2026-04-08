# vulture_whitelist.py
# Names used by external frameworks that vulture cannot detect statically.

handler  # Mangum Lambda entry point, referenced by SAM template.yaml
application  # ASGI app consumed by Mangum handler
tracer  # AWS X-Ray PowerTools, used via @tracer.capture_lambda_handler
export_db  # FastAPI route handler, registered by @router.post()
health  # FastAPI route handler, registered by @router.get()
anthropic_api_key  # Pydantic Settings field
recipe_api_key  # Pydantic Settings field
recipe_api_base_url  # Pydantic Settings field
log_level  # Pydantic Settings field
rate_limit_per_hour  # Pydantic Settings field
model_config  # Pydantic v2 model configuration
name  # ParsedIngredient Pydantic field
quantity  # ParsedIngredient Pydantic field
unit  # ParsedIngredient Pydantic field
unit_price  # ParsedIngredient Pydantic field
# recipe_api/schemas.py Pydantic fields
description  # RecipeApiIngredient field
category  # RecipeApiIngredient field
# recipes/schemas.py Pydantic fields
api_ingredient_id  # RecipeIngredientOut field
canonical_name  # RecipeIngredientOut field
external_id  # RecipeOut / RecipeSearchResult field
title  # RecipeOut / RecipeSearchResult field
dietary_flags  # RecipeOut / RecipeSearchResult field
