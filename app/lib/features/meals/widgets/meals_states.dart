import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// A centred icon + message + optional action — the shared shape for every
/// Meals empty/no-results/error state (AC-MEAL-10). No shared design-system
/// primitive for this exists yet (unlike RN's `EmptyState`/`ErrorState`), so
/// this stays local to Meals rather than inventing one on another module's
/// behalf.
class MealsMessagePanel extends StatelessWidget {
  const MealsMessagePanel({
    required this.icon,
    required this.title,
    this.message,
    this.action,
    super.key,
  });

  final IconData icon;
  final String title;
  final String? message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: EdgeInsets.symmetric(
        horizontal: tokens.spacing.xl,
        vertical: tokens.spacing.xxl,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(icon, size: 40, color: colorScheme.onSurfaceVariant),
          SizedBox(height: tokens.spacing.md),
          Text(
            title,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          if (message != null) ...<Widget>[
            SizedBox(height: tokens.spacing.xs),
            Text(
              message!,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
          if (action != null) ...<Widget>[
            SizedBox(height: tokens.spacing.lg),
            action!,
          ],
        ],
      ),
    );
  }
}
