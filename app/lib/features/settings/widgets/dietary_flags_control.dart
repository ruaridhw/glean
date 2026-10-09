import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/design_system/design_system.dart';

import '../settings_presentation.dart';

/// Toggleable dietary-flag chips shared by Settings and the first-run
/// onboarding flow (FLUTTER_MIGRATION.md §6). Built on the themed
/// `FilterChip` (`chipTheme` in `theme.dart`) rather than a hand-rolled pill
/// `Pressable` — AC-DS-05.
///
/// Each tap fires exactly one `selectionClick` (AC-HAP-05 — "dietary chips
/// ... → selectionClick"), never `mediumImpact`: a chip toggle is a
/// selection change, not the separate "committed save" rung, even though the
/// caller does persist it immediately (see `SettingsScreen`'s doc comment).
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
