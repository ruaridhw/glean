import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/design_system/design_system.dart';

import '../settings_presentation.dart';

/// Toggleable dietary-flag chips shared by Settings and onboarding, on the themed `FilterChip`. Each tap fires
/// exactly one `selectionClick`, never `mediumImpact`: a chip toggle is a selection change, not a committed
/// save, even though the caller persists it immediately.
class DietaryFlagsControl extends ConsumerWidget {
  const DietaryFlagsControl({
    super.key,
    required this.selected,
    required this.onToggle,
  });

  final Set<String> selected;
  final void Function(String flag, bool isSelected) onToggle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppTokens tokens = context.tokens;
    return Wrap(
      spacing: tokens.spacing.sm,
      runSpacing: tokens.spacing.sm,
      children: <Widget>[
        for (final String flag in dietaryOptions)
          FilterChip(
            label: Text(flag),
            selected: selected.contains(flag),
            onSelected: (bool isSelected) {
              ref.read(hapticsProvider).selectionClick();
              onToggle(flag, isSelected);
            },
          ),
      ],
    );
  }
}

/// Settings' card chrome around [DietaryFlagsControl]. Onboarding uses the bare chips under its own question
/// heading instead.
class DietaryPreferencesCard extends StatelessWidget {
  const DietaryPreferencesCard({
    super.key,
    required this.selected,
    required this.onToggle,
  });

  final Set<String> selected;
  final void Function(String flag, bool isSelected) onToggle;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Card(
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.md),
        child: DietaryFlagsControl(selected: selected, onToggle: onToggle),
      ),
    );
  }
}
