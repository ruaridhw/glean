import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:go_router/go_router.dart';

/// Empty list state — the whole list is a to-do, and the natural next step
/// is the tab that actually generates shopping needs.
class ShopEmptyState extends ConsumerWidget {
  const ShopEmptyState({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppTokens tokens = context.tokens;
    return Center(
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: tokens.spacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(
              Icons.shopping_cart_outlined,
              size: 40,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            SizedBox(height: tokens.spacing.md),
            Text(
              'Your shopping list is empty',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            SizedBox(height: tokens.spacing.xs),
            Text(
              "Plan some meals and we'll figure out what you need.",
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            SizedBox(height: tokens.spacing.lg),
            FilledButton(
              onPressed: () {
                ref.read(hapticsProvider).lightImpact();
                context.go(AppRoutes.plan.path);
              },
              child: const Text('Go to meal plan'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Shown when `shoppingListProvider` itself errors — a drift stream failing
/// is not expected in practice, but it must never render as a silently empty
/// list.
class ShopErrorState extends StatelessWidget {
  const ShopErrorState({super.key});

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Center(
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(
              Icons.error_outline_rounded,
              size: 40,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            SizedBox(height: tokens.spacing.md),
            Text(
              'Could not load your shopping list',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ],
        ),
      ),
    );
  }
}
