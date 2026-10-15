import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// The at-a-glance summary row at the top of Settings (dinners, servings,
/// diets, tolerance) — display-only, ported from RN's `StatsRow` usage in
/// `settings/index.tsx`. Purely presentational: it never drives haptics or
/// persistence itself, unlike the interactive controls below it.
class SettingsStatsRow extends StatelessWidget {
  const SettingsStatsRow({
    super.key,
    required this.dinners,
    required this.servings,
    required this.dietCount,
    required this.tolerancePercent,
  });

  final int dinners;
  final int servings;
  final int dietCount;
  final int tolerancePercent;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final List<(String, String)> stats = <(String, String)>[
      ('$dinners', 'Dinners'),
      ('$servings', 'Servings'),
      ('$dietCount', 'Diets'),
      ('$tolerancePercent%', 'Tolerance'),
    ];
    return Card(
      child: Padding(
        padding: EdgeInsets.symmetric(vertical: tokens.spacing.md),
        child: Row(
          children: <Widget>[
            for (final (String value, String label) in stats)
              Expanded(
                child: Column(
                  children: <Widget>[
                    Text(value, style: Theme.of(context).textTheme.titleLarge),
                    Text(label, style: Theme.of(context).textTheme.bodySmall),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
