import 'package:flutter/material.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/design_system/design_system.dart';

import '../pantry_presentation.dart';
import 'pantry_item_row.dart';

/// One category section: a header (icon, label, count) plus its rows.
///
/// Deliberately not wrapped in an `AnimatedList` — a [SwipeToDeleteRow]'s
/// `Dismissible` already animates its own removal gap closed (AC-TRN-02);
/// adding a second removal animation for the same item would fight it
/// (matches the same call in `lib/features/meals/meals_screen.dart`).
class PantrySectionView extends StatelessWidget {
  const PantrySectionView({
    super.key,
    required this.section,
    required this.onDelete,
  });

  final PantrySection section;
  final ValueChanged<PantryItemView> onDelete;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Padding(
      padding: EdgeInsets.only(bottom: tokens.spacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(
                section.meta.icon,
                size: 18,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
              SizedBox(width: tokens.spacing.sm),
              Text(
                section.meta.label,
                style: Theme.of(context).textTheme.titleSmall,
              ),
              SizedBox(width: tokens.spacing.sm),
              Text(
                '${section.items.length}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
          SizedBox(height: tokens.spacing.sm),
          for (final PantryItemView item in section.items)
            Padding(
              padding: EdgeInsets.only(bottom: tokens.spacing.sm),
              child: PantryItemRow(item: item, onDelete: () => onDelete(item)),
            ),
        ],
      ),
    );
  }
}
