/// Route path and name constants for the whole app.
library;

/// A route's path (used to build the `go_router` table) and its unique name
/// (used at call sites instead of a literal string).
class RouteSpec {
  const RouteSpec(this.path, this.name);

  final String path;
  final String name;
}

/// Every route in the app, grouped by where it sits in the navigation structure.
abstract final class AppRoutes {
  // --- Auth (outside the tab shell; shown pre-authentication) ---
  static const RouteSpec signIn = RouteSpec('/sign-in', 'sign-in');

  // --- Tab shell branches. Pantry is the landing tab. ---
  static const RouteSpec pantry = RouteSpec('/pantry', 'pantry');

  static const RouteSpec meals = RouteSpec('/meals', 'meals');
  // No `mealsSearch` route: search is inline in `MealsScreen`.
  static const RouteSpec mealsImport = RouteSpec(
    '/meals/import',
    'meals-import',
  );
  // ':id' is a path segment, not an `extra`, so cold-start deep links work.
  static const RouteSpec mealsDetail = RouteSpec('/meals/:id', 'meals-detail');

  static const RouteSpec plan = RouteSpec('/plan', 'plan');
  // A planned meal's saved recipe, pushed inside the Plan tab so Back returns to Plan.
  static const RouteSpec planRecipe = RouteSpec(
    '/plan/recipe/:id',
    'plan-recipe',
  );

  static const RouteSpec shop = RouteSpec('/shop', 'shop');

  static const RouteSpec settings = RouteSpec('/settings', 'settings');

  // --- Intake: a modal task outside every tab branch, shared by Pantry and Shop. ---
  static const RouteSpec intakeScan = RouteSpec('/intake/scan', 'intake-scan');
  static const RouteSpec intakeScanProgress = RouteSpec(
    '/intake/scan-progress',
    'intake-scan-progress',
  );
  static const RouteSpec intakeDescribePantry = RouteSpec(
    '/intake/describe/pantry',
    'intake-describe-pantry',
  );
  static const RouteSpec intakeDescribeShop = RouteSpec(
    '/intake/describe/shop',
    'intake-describe-shop',
  );
  static const RouteSpec intakeManualEntry = RouteSpec(
    '/intake/manual-entry',
    'intake-manual-entry',
  );
  // One review screen for both flows; `ReviewArgs.destination` picks which.
  static const RouteSpec intakeReview = RouteSpec(
    '/intake/review',
    'intake-review',
  );

  /// Recoverable error page: target for unmatched locations and malformed
  /// path parameters (e.g. a non-numeric recipe id).
  static const RouteSpec error = RouteSpec('/error', 'error');

  /// Builds a concrete path for [mealsDetail] — the one place that formats
  /// this path, so feature code never hand-interpolates it.
  static String mealsDetailPath(String id) => '/meals/$id';

  /// Builds a concrete path for [planRecipe].
  static String planRecipePath(String id) => '/plan/recipe/$id';
}
