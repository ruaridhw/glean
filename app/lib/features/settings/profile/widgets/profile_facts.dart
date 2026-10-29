import 'package:flutter/material.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/design_system/design_system.dart';

import '../profile_presentation.dart';

/// A read-only taste ledger shared by the saved profile and final interview review.
class ProfileFacts extends StatelessWidget {
  const ProfileFacts({
    required this.profile,
    this.memoryTitle = 'Also remembered',
    super.key,
  });

  final HouseholdProfile profile;
  final String memoryTitle;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final text = Theme.of(context).textTheme;
    final rows = <(String, String)>[
      (
        'Favourite dinners',
        profile.favouriteMeals.map((meal) => meal.text).join(', '),
      ),
      (
        'Never on the plan',
        <String>[
          ...profile.dislikedIngredients,
          ...profile.cuisinesAvoided,
        ].join(', '),
      ),
      (
        'Love to eat',
        <String>[
          ...profile.lovedIngredients,
          ...profile.cuisinesLiked,
        ].join(', '),
      ),
      ('Your week', profile.habits),
      ('At the table', profile.household),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        for (final row in rows) ...<Widget>[
          Padding(
            padding: EdgeInsets.symmetric(vertical: tokens.spacing.md),
            child: LayoutBuilder(
              builder: (context, constraints) {
                final label = Text(
                  row.$1.toUpperCase(),
                  style: text.labelSmall,
                );
                final value = Text(
                  row.$2.isEmpty ? 'Not answered' : row.$2,
                  style: text.bodyMedium,
                );
                if (MediaQuery.textScalerOf(context).scale(14) > 22 ||
                    constraints.maxWidth < 240) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      label,
                      SizedBox(height: tokens.spacing.sm),
                      value,
                    ],
                  );
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    SizedBox(width: 96, child: label),
                    SizedBox(width: tokens.spacing.md),
                    Expanded(child: value),
                  ],
                );
              },
            ),
          ),
          const Divider(height: 1),
        ],
        SizedBox(height: tokens.spacing.lg),
        Text(memoryTitle, style: text.titleMedium),
        SizedBox(height: tokens.spacing.sm),
        if (profile.proteinTargets.isNotEmpty)
          Text(profile.proteinTargets.map(proteinTargetLabel).join('\n')),
        if (profile.spiceTolerance case final SpiceTolerance spice)
          Text('Spice: ${spiceLabel(spice)}'),
        for (final note in profile.notes) ...<Widget>[
          SizedBox(height: tokens.spacing.sm),
          Text(note.text, style: text.bodySmall),
        ],
        if (profile.proteinTargets.isEmpty &&
            profile.spiceTolerance == null &&
            profile.notes.isEmpty)
          const Text('No other saved facts yet.'),
      ],
    );
  }
}
