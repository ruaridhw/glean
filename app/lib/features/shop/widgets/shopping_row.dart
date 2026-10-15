import 'package:flutter/material.dart';
import 'package:glean/data/models/shopping_list_item_view.dart';
import 'package:glean/design_system/design_system.dart';

import '../presentation.dart';

/// One row in the shopping list. The caller wraps it in `SwipeToDeleteRow`; this widget only renders content and
/// the tap-to-toggle, so the delete affordance is owned in one place.
class ShoppingRow extends StatelessWidget {
  const ShoppingRow({
    required this.item,
    required this.onToggle,
    this.onLongPress,
    super.key,
  });

  final ShoppingListItemView item;
  final VoidCallback onToggle;

  /// Opens the move-to-section choice.
  final VoidCallback? onLongPress;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    final AppTokens tokens = context.tokens;
    final bool checked = item.isChecked;
    final String? subtitle = checked
        ? null
        : forRecipeSubtitle(item.recipeTitles);

    return Card(
      color: checked ? colorScheme.surfaceContainerHighest : null,
      child: InkWell(
        onTap: onToggle,
        onLongPress: onLongPress,
        borderRadius: BorderRadius.circular(tokens.radius.lg),
        child: Padding(
          padding: EdgeInsets.symmetric(
            horizontal: tokens.spacing.lg,
            vertical: tokens.spacing.md,
          ),
          child: Row(
            children: <Widget>[
              _CheckCircle(checked: checked),
              SizedBox(width: tokens.spacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
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
                    if (subtitle != null)
                      Text(
                        subtitle,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                        ),
                      ),
                  ],
                ),
              ),
              // A plan-derived row is tagged on every render, not just announced once at insertion (see
              // `presentation.dart`'s `isPlanDerived`).
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
          ? Icon(Icons.check_rounded, size: 14, color: colorScheme.onPrimary)
          : null,
    );
  }
}
