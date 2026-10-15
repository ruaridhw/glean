import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'app_routes.dart';

/// Recoverable error page for a navigation failure.
///
/// Used both as the [GoRouter.errorBuilder] (an unmatched location) and as
/// the target of a route-level redirect guard (e.g. a malformed path
/// parameter). Both back affordances fall back to the Pantry tab rather than
/// calling `pop()` blindly — the RN bug this replaces called `router.back()`
/// on a cold-start deep link with nothing to pop, which hung on a permanent
/// spinner (§11, AC-MEAL-12). There is always a way out.
///
/// Feature waves needing a "valid route, no matching data" error (e.g. a
/// deep link to a recipe id that doesn't exist) should reuse this widget
/// rather than inventing another one.
class RouteErrorScreen extends StatelessWidget {
  const RouteErrorScreen({required this.message, super.key});

  final String message;

  void _recover(BuildContext context) {
    if (context.canPop()) {
      context.pop();
    } else {
      context.go(AppRoutes.pantry.path);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(leading: BackButton(onPressed: () => _recover(context))),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded, size: 48),
              const SizedBox(height: 16),
              Text(message, textAlign: TextAlign.center),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: () => _recover(context),
                child: const Text('Back to Pantry'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
