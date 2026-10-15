import 'package:flutter/material.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/design_system/design_system.dart';

import '../pantry_presentation.dart';
import 'pantry_empty_state.dart';
import 'pantry_expiry_banner.dart';
import 'pantry_filter_chips.dart';
import 'pantry_section_view.dart';

/// The populated pantry body: expiry banner, filter chips and the grouped,
/// sectioned list.
///
/// AC-PAN-12: the selected filter is clamped to a key that still exists in
/// [items] on every build, rather than trusting the caller's stored
/// selection — so deleting the last item of the selected category can never
/// strand the view on a filter that now matches nothing (RN's bug: a blank
/// body with no chip selected). This is computed fresh each build, not
/// "healed" by writing back to the caller's state, so it holds even for a
/// single frame where the stream has just re-emitted without user input.
class PantryBody extends StatelessWidget {
  const PantryBody({
    super.key,
    required this.items,
    required this.filterKey,
    required this.onFilterChanged,
    required this.onDelete,
  });

  final List<PantryItemView> items;

  /// Null means "All". May be stale (naming a category no longer present);
  /// see the class doc for why that's handled here, not upstream.
  final String? filterKey;
  final ValueChanged<String?> onFilterChanged;
  final ValueChanged<PantryItemView> onDelete;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const PantryEmptyState();

    final AppTokens tokens = context.tokens;
    final List<PantrySection> sections = groupPantryItems(items);
    final String? effectiveFilterKey =
        sections.any((PantrySection s) => s.meta.key == filterKey)
        ? filterKey
        : null;
    final int expiringCount = items
        .where((PantryItemView i) => isExpiringSoon(i))
        .length;
    final List<PantrySection> visibleSections = effectiveFilterKey == null
        ? sections
        : sections
              .where((PantrySection s) => s.meta.key == effectiveFilterKey)
              .toList();

    return Padding(
      padding: EdgeInsets.all(tokens.spacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          PantryExpiryBanner(expiringCount: expiringCount),
          PantryFilterChips(
            sections: sections,
            totalCount: items.length,
            selectedKey: effectiveFilterKey,
            onSelect: onFilterChanged,
          ),
          SizedBox(height: tokens.spacing.md),
          Expanded(
            child: ListView(
              children: <Widget>[
                for (final PantrySection section in visibleSections)
                  PantrySectionView(section: section, onDelete: onDelete),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
