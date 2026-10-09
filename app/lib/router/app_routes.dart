/// Route path and name constants for the whole app.
///
/// Every call site (feature screens, router wiring, tests) references these
/// instead of hand-writing literals — see FLUTTER_MIGRATION.md §2/§4. Names
/// are unique and are what `context.goNamed`/`context.pushNamed` should use;
/// paths are what the [GoRouter] table is built from.
library;

/// A route's path (used to build the `go_router` table) and its unique name
/// (used at call sites instead of a literal string).
class RouteSpec {
  const RouteSpec(this.path, this.name);

  final String path;
  final String name;
}

/// Central registry of every route in the app. Grouped by where it sits in
/// the navigation structure — see [tabBranchRoots] and [intakeRoutes] for the
/// two groups the router-table test asserts on.
abstract final class AppRoutes {
  // --- Auth (outside the tab shell; shown pre-authentication) ---
  static const RouteSpec signIn = RouteSpec('/sign-in', 'sign-in');

  // --- Tab shell branches. Pantry is the landing tab (AC-SET-05). ---
  static const RouteSpec pantry = RouteSpec('/pantry', 'pantry');

  static const RouteSpec meals = RouteSpec('/meals', 'meals');
  // No `mealsSearch` route: search is a single inline `TextField` in the
  // Search segment of `MealsScreen` itself (AC-MEAL-07 — "one search
  // affordance", dropping both the fake search pill and the separate
  // pushed screen). A route that still resolved to a screen would leave
  // that dropped second affordance reachable by deep link, which is
  // exactly what the criterion rules out.
  static const RouteSpec mealsImport = RouteSpec(
    '/meals/import',
    'meals-import',
  );
  // ':id' is a path segment (not a typed `extra`) because a cold-start deep
  // link has no in-memory object to pass — see [mealsDetailPath] and
  // AC-MEAL-12.
  static const RouteSpec mealsDetail = RouteSpec('/meals/:id', 'meals-detail');

  static const RouteSpec plan = RouteSpec('/plan', 'plan');

  static const RouteSpec shop = RouteSpec('/shop', 'shop');

  static const RouteSpec settings = RouteSpec('/settings', 'settings');

  // --- Intake — a modal task, deliberately outside every tab branch
  // (AC-PAN-04): the tab bar cannot render over the camera because the tab
  // shell isn't in the widget tree at all while these are active. Shared by
  // both the Pantry and Shop entry points. ---
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
  // One review screen for both pantry and shop intake (AC-PAN-05) — which
  // flow it's completing travels as typed `extra` (`ReviewArgs.destination`),
  // not as a second route.
  static const RouteSpec intakeReview = RouteSpec(
    '/intake/review',
    'intake-review',
  );

  /// Recoverable error page — the [GoRouter.errorBuilder] target for an
  /// unmatched location, and the redirect target for a malformed path
  /// parameter (e.g. a non-numeric recipe id). Never a dead end (AC-MEAL-12).
  static const RouteSpec error = RouteSpec('/error', 'error');

  /// Builds a concrete path for [mealsDetail] — the one place that formats
  /// this path, so feature code never hand-interpolates it.
  static String mealsDetailPath(String id) => '/meals/$id';

  /// The five tab-shell branch roots, in tab-bar order. Asserted by the
  /// route-table test (AC-TEST-14): exactly five, Pantry first.
  static const List<RouteSpec> tabBranchRoots = <RouteSpec>[
    pantry,
    meals,
    plan,
    shop,
    settings,
  ];

  /// Every intake route — must resolve outside the tab shell (AC-PAN-04).
  static const List<RouteSpec> intakeRoutes = <RouteSpec>[
    intakeScan,
    intakeScanProgress,
    intakeDescribePantry,
    intakeDescribeShop,
    intakeManualEntry,
    intakeReview,
  ];

  /// Every route in the app, for name-uniqueness checks and general
  /// introspection. Keep in sync when adding a route.
  static const List<RouteSpec> all = <RouteSpec>[
    signIn,
    ...tabBranchRoots,
    mealsImport,
    mealsDetail,
    ...intakeRoutes,
    error,
  ];
}
