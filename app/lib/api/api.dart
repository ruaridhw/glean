/// Barrel export for the API module. Other modules (DATA, features) should
/// import this rather than reaching into `lib/api/**` file-by-file.
library;

export 'api_client.dart';
export 'api_exception.dart';
export 'models/meal_plan.dart';
export 'models/parsed_ingredient.dart';
export 'models/receipts.dart';
export 'models/recipes.dart';
export 'models/shopping.dart';
export 'providers/api_providers.dart';
export 'providers/meal_plan_providers.dart';
export 'providers/receipts_providers.dart';
export 'providers/recipe_providers.dart';
export 'providers/shopping_providers.dart';
export 'text_input.dart';
