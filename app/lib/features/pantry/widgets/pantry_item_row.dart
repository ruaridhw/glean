import 'package:flutter/material.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/design_system/design_system.dart';

import '../pantry_presentation.dart';
import 'quantity_edit_sheet.dart';

GleanBadgeTone _toneFor(ExpiryTone tone) => switch (tone) {
  ExpiryTone.expired => GleanBadgeTone.danger,
  ExpiryTone.soon => GleanBadgeTone.warning,
  ExpiryTone.later => GleanBadgeTone.neutral,
};

/// One pantry row: swipe-to-delete (AC-UX-01 — exactly one delete
/// affordance, replacing RN's row-swipe **and** trash `IconButton` on the
/// same row) and a tap opens the quantity/unit/expiry sheet (AC-PAN-07).
class PantryItemRow extends StatelessWidget {
  const PantryItemRow({super.key, required this.item, required this.onDelete});

  final PantryItemView item;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ExpiryBadge? badge = expiryBadgeFor(item.expiryDate);

    return SwipeToDeleteRow(
      dismissibleKey: ValueKey<int>(item.id),
      onDelete: onDelete,
      child: Card(
        child: InkWell(
          borderRadius: BorderRadius.circular(tokens.radius.lg),
          onTap: () => QuantityEditSheet.show(context, item),
          child: Padding(
            padding: EdgeInsets.symmetric(
              horizontal: tokens.spacing.lg,
              vertical: tokens.spacing.md,
            ),
            child: Row(
              children: <Widget>[
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        item.canonicalName,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(
                        formatPantryQuantity(item.quantity, item.unit),
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ],
                  ),
                ),
                if (badge != null)
                  GleanBadge(label: badge.label, tone: _toneFor(badge.tone)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
