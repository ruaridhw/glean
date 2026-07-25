import 'package:flutter/material.dart';
import 'package:glean/data/models/shopping_list_item_view.dart';
import 'package:glean/design_system/design_system.dart';

import '../presentation.dart';

/// One row in the shopping list. Wrapped in `SwipeToDeleteRow` by the caller
/// — this widget only renders content and the tap-to-toggle, keeping the
/// delete affordance owned by exactly one place (AC-UX-01: RN carried both
/// this row's swipe *and* a separate "×" `Pressable` on checked rows).
class ShoppingRow extends StatelessWidget {
  const ShoppingRow({required this.item, required this.onToggle, super.key});

  final ShoppingListItemView item;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    final AppTokens tokens = context.tokens;
    final bool checked = item.isChecked;

    return Card(
      color: checked ? colorScheme.surfaceContainerHighest : null,
      child: InkWell(
        onTap: onToggle,
        borderRadius: BorderRadius.circular(tokens.radius.lg),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            children: <Widget>[
              _CheckCircle(checked: checked),
              SizedBox(width: tokens.spacing.md),
              Expanded(
                child: Text(
                  formatShoppingItemLabel(item),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    decoration: checked
                        ? TextDecoration.lineThrough
                        : TextDecoration.none,
                    color: checked
                        ? colorScheme.onSurfaceVariant
                        : colorScheme.onSurface,
                  ),
                ),
              ),
              // AC-SHOP-05: a plan-derived row is tagged on every render, not
              // just announced once at insertion (which happens outside this
              // module — see `presentation.dart`'s `isPlanDerived` doc).
              if (isPlanDerived(item)) ...<Widget>[
                SizedBox(width: tokens.spacing.sm),
                const GleanBadge(
                  label: 'From plan',
                  tone: GleanBadgeTone.primary,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _CheckCircle extends StatelessWidget {
  const _CheckCircle({required this.checked});

  final bool checked;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Container(
      width: 24,
      height: 24,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: checked ? colorScheme.primary : Colors.transparent,
        border: Border.all(
          color: checked ? colorScheme.primary : colorScheme.outlineVariant,
          width: 2,
        ),
      ),
      child: checked
          ? const Icon(Icons.check_rounded, size: 14, color: Colors.white)
          : null,
    );
  }
}
