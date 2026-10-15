import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

import 'pantry_add_sheet.dart';

/// Empty pantry state. The single CTA opens the same `+` sheet the populated
/// screen uses (AC-PAN-03) — there is exactly one place all three intake
/// modes live, not a separate empty-state-only shortcut that only covers two
/// of them (the RN app's empty state offered Scan/Describe but not Manual).
class PantryEmptyState extends StatelessWidget {
  const PantryEmptyState({super.key});

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
              Icons.shopping_basket_rounded,
              size: 48,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            SizedBox(height: tokens.spacing.lg),
            Text(
              'Your pantry is empty',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            SizedBox(height: tokens.spacing.sm),
            Text(
              'Scan a receipt, describe what you bought, or add an item '
              'yourself to get started.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            SizedBox(height: tokens.spacing.xl),
            FilledButton(
              onPressed: () => PantryAddSheet.show(context),
              child: const Text('Add items'),
            ),
          ],
        ),
      ),
    );
  }
}
