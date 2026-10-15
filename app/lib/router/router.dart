/// The `go_router` route table: a [StatefulShellRoute.indexedStack] for the five tabs, plus the intake
/// flow and sign-in as top-level siblings outside it. Path/name constants are in `app_routes.dart`.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../auth/auth.dart';
import '../features/auth/sign_in_screen.dart';
import '../features/intake/manual_entry_screen.dart';
import '../features/intake/pantry_describe_screen.dart';
import '../features/intake/review_screen.dart';
import '../features/intake/scan_progress_screen.dart';
import '../features/intake/scan_screen.dart';
import '../features/intake/shop_describe_screen.dart';
import '../features/meals/meal_detail_screen.dart';
import '../features/meals/meals_import_screen.dart';
import '../features/meals/meals_screen.dart';
import '../features/onboarding/onboarding_gate.dart';
import '../features/pantry/pantry_screen.dart';
import '../features/plan/plan_screen.dart';
import '../features/settings/settings_screen.dart';
import '../features/shop/shop_screen.dart';
import 'app_routes.dart';
import 'app_shell.dart';
import 'intake_params.dart';
import 'route_error_screen.dart';

/// Bridges [authStatusProvider] changes into `GoRouter`'s `refreshListenable`
/// so a sign-out or expiry flip re-evaluates [_authRedirect] immediately,
/// without the router itself being torn down and rebuilt.
class _AuthRefreshNotifier extends ChangeNotifier {
  _AuthRefreshNotifier(Ref ref) {
    ref.listen<AuthStatus>(authStatusProvider, (
      AuthStatus? previous,
      AuthStatus next,
    ) {
      notifyListeners();
    });
  }
}

/// Redirect gates on `signedOut` only. `expired` falls through: the user keeps reading local data behind
/// the banner that gates AI-backed actions.
String? _authRedirect(AuthStatus status, GoRouterState state) {
  final bool atSignIn = state.matchedLocation == AppRoutes.signIn.path;
  if (status == AuthStatus.signedOut) {
    return atSignIn ? null : AppRoutes.signIn.path;
  }
  return atSignIn ? AppRoutes.pantry.path : null;
}

/// Riverpod provider for the app's [GoRouter]. `lib/app.dart` watches this.
final Provider<GoRouter> goRouterProvider = Provider<GoRouter>((Ref ref) {
  final _AuthRefreshNotifier refresh = _AuthRefreshNotifier(ref);
  ref.onDispose(refresh.dispose);

  return GoRouter(
    initialLocation: AppRoutes.pantry.path,
    refreshListenable: refresh,
    redirect: (BuildContext context, GoRouterState state) =>
        _authRedirect(ref.read(authStatusProvider), state),
    errorBuilder: (BuildContext context, GoRouterState state) =>
        RouteErrorScreen(
          message: state.error?.toString() ?? 'This page could not be found.',
        ),
    routes: <RouteBase>[
      GoRoute(
        path: AppRoutes.signIn.path,
        name: AppRoutes.signIn.name,
        builder: (BuildContext context, GoRouterState state) =>
            const SignInScreen(),
      ),

      // --- Intake: modal task, outside every tab branch. ---
      GoRoute(
        path: AppRoutes.intakeScan.path,
        name: AppRoutes.intakeScan.name,
        builder: (BuildContext context, GoRouterState state) {
          final Object? extra = state.extra;
          return ScanScreen(args: extra is ScanArgs ? extra : const ScanArgs());
        },
      ),
      GoRoute(
        path: AppRoutes.intakeScanProgress.path,
        name: AppRoutes.intakeScanProgress.name,
        builder: (BuildContext context, GoRouterState state) {
          final Object? extra = state.extra;
          if (extra is! ScanProgressArgs) {
            return const RouteErrorScreen(message: 'Nothing to scan.');
          }
          return ScanProgressScreen(args: extra);
        },
      ),
      GoRoute(
        path: AppRoutes.intakeDescribePantry.path,
        name: AppRoutes.intakeDescribePantry.name,
        builder: (BuildContext context, GoRouterState state) =>
            const PantryDescribeScreen(),
      ),
      GoRoute(
        path: AppRoutes.intakeDescribeShop.path,
        name: AppRoutes.intakeDescribeShop.name,
        builder: (BuildContext context, GoRouterState state) =>
            const ShopDescribeScreen(),
      ),
      GoRoute(
        path: AppRoutes.intakeManualEntry.path,
        name: AppRoutes.intakeManualEntry.name,
        builder: (BuildContext context, GoRouterState state) =>
            const ManualEntryScreen(),
      ),
      GoRoute(
        path: AppRoutes.intakeReview.path,
        name: AppRoutes.intakeReview.name,
        builder: (BuildContext context, GoRouterState state) {
          final Object? extra = state.extra;
          if (extra is! ReviewArgs) {
            return const RouteErrorScreen(message: 'Nothing to review.');
          }
          return ReviewScreen(args: extra);
        },
      ),

      GoRoute(
        path: AppRoutes.error.path,
        name: AppRoutes.error.name,
        builder: (BuildContext context, GoRouterState state) {
          final Object? extra = state.extra;
          return RouteErrorScreen(
            message: extra is String ? extra : 'This page could not be found.',
          );
        },
      ),

      // --- The five-tab shell. Each branch is its own Navigator, so a push in one tab survives switching away and back. ---
      StatefulShellRoute.indexedStack(
        // Gates the whole tab shell behind first-run setup. Wrapped here, not at `MaterialApp.router`, so
        // `OnboardingScreen` has a `GoRouter` in its context.
        builder:
            (
              BuildContext context,
              GoRouterState state,
              StatefulNavigationShell navigationShell,
            ) => OnboardingGate(
              child: AppShell(navigationShell: navigationShell),
            ),
        branches: <StatefulShellBranch>[
          StatefulShellBranch(
            routes: <RouteBase>[
              GoRoute(
                path: AppRoutes.pantry.path,
                name: AppRoutes.pantry.name,
                builder: (BuildContext context, GoRouterState state) =>
                    const PantryScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: <RouteBase>[
              GoRoute(
                path: AppRoutes.meals.path,
                name: AppRoutes.meals.name,
                builder: (BuildContext context, GoRouterState state) =>
                    const MealsScreen(),
                routes: <RouteBase>[
                  // The literal 'import' segment must be declared before
                  // the `:id` catch-all below — go_router matches siblings
                  // in declaration order, and `:id` would otherwise
                  // swallow `/meals/import` as an id.
                  GoRoute(
                    path: 'import',
                    name: AppRoutes.mealsImport.name,
                    builder: (BuildContext context, GoRouterState state) =>
                        const MealsImportScreen(),
                  ),
                  GoRoute(
                    path: ':id',
                    name: AppRoutes.mealsDetail.name,
                    // Guards the decode: a malformed (non-numeric) id never reaches the screen. "Valid id, no such recipe"
                    // is handled by `MealDetailScreen`.
                    redirect: (BuildContext context, GoRouterState state) {
                      final String? id = state.pathParameters['id'];
                      if (id == null || int.tryParse(id) == null) {
                        return AppRoutes.error.path;
                      }
                      return null;
                    },
                    builder: (BuildContext context, GoRouterState state) =>
                        MealDetailScreen(recipeId: state.pathParameters['id']!),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: <RouteBase>[
              GoRoute(
                path: AppRoutes.plan.path,
                name: AppRoutes.plan.name,
                builder: (BuildContext context, GoRouterState state) =>
                    const PlanScreen(),
                routes: <RouteBase>[
                  GoRoute(
                    path: 'recipe/:id',
                    name: AppRoutes.planRecipe.name,
                    // Same malformed-id guard as `AppRoutes.mealsDetail`.
                    redirect: (BuildContext context, GoRouterState state) {
                      final String? id = state.pathParameters['id'];
                      if (id == null || int.tryParse(id) == null) {
                        return AppRoutes.error.path;
                      }
                      return null;
                    },
                    builder: (BuildContext context, GoRouterState state) =>
                        MealDetailScreen(recipeId: state.pathParameters['id']!),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: <RouteBase>[
              GoRoute(
                path: AppRoutes.shop.path,
                name: AppRoutes.shop.name,
                builder: (BuildContext context, GoRouterState state) =>
                    const ShopScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: <RouteBase>[
              GoRoute(
                path: AppRoutes.settings.path,
                name: AppRoutes.settings.name,
                builder: (BuildContext context, GoRouterState state) =>
                    const SettingsScreen(),
              ),
            ],
          ),
        ],
      ),
    ],
  );
});
