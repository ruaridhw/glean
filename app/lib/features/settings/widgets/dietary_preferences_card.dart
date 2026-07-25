import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

import 'dietary_flags_control.dart';

/// Settings' card chrome around the shared [DietaryFlagsControl] — kept
/// separate from the control itself so onboarding (no card, just the bare
/// chips under a question heading) can reuse it without this wrapper.
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
