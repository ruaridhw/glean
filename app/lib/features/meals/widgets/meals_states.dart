import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// A centred icon + message + optional action: the shared shape for every Meals empty/no-results/error state.
/// Local to Meals since no design-system primitive exists for it.
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
