import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:go_router/go_router.dart';

import 'app_routes.dart';

/// Recoverable error page for a navigation failure: the [GoRouter.errorBuilder] and the target of
/// route-level redirect guards. Both back affordances fall back to the Pantry tab rather than calling
/// `pop()` blindly, since a cold-start deep link may have nothing to pop.
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
          padding: EdgeInsets.all(context.tokens.spacing.xl),
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
