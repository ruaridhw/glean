import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/design_system/design_system.dart';

import '../pantry_presentation.dart';

/// The "All" + per-category filter row. Selection fires `selectionClick`
/// (AC-HAP-05) via the themed [FilterChip] — no hand-rolled pill button
/// (AC-DS-05).
class PantryFilterChips extends ConsumerWidget {
  const PantryFilterChips({
    super.key,
    required this.sections,
    required this.totalCount,
    required this.selectedKey,
    required this.onSelect,
  });

  final List<PantrySection> sections;
  final int totalCount;

  /// Null means "All".
  final String? selectedKey;
  final ValueChanged<String?> onSelect;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppTokens tokens = context.tokens;
    void select(String? key) {
      ref.read(hapticsProvider).selectionClick();
      onSelect(key);
    }

    return Wrap(
      spacing: tokens.spacing.sm,
      runSpacing: tokens.spacing.sm,
      children: <Widget>[
        FilterChip(
          label: Text('All · $totalCount'),
          selected: selectedKey == null,
          onSelected: (bool _) => select(null),
        ),
        for (final PantrySection section in sections)
          FilterChip(
            label: Text('${section.meta.shortLabel} · ${section.items.length}'),
            selected: selectedKey == section.meta.key,
            onSelected: (bool _) => select(section.meta.key),
          ),
      ],
    );
  }
}
