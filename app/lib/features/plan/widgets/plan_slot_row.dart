/// One row in the Dinners list — either a filled entry (swipe-to-delete,
/// mark-cooked) or an empty, tappable "Add a dinner" slot.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/design_system/design_system.dart';

import '../actions.dart';
import '../presentation.dart';

class PlanSlotRow extends ConsumerWidget {
  const PlanSlotRow({super.key, required this.slot, required this.onEmptyTap});

  final PlanSlot slot;
  final VoidCallback onEmptyTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final MealPlanEntryView? entry = slot.entry;
    if (entry == null) {
      return _EmptySlotRow(onTap: onEmptyTap);
    }
    return SwipeToDeleteRow(
      dismissibleKey: ValueKey<int>(entry.id),
      onDelete: () => deleteEntryWithUndo(context, ref, entry),
      child: _FilledSlotRow(
        entry: entry,
        onCooked: () => markCookedWithUndo(context, ref, entry),
      ),
    );
  }
}

class _EmptySlotRow extends StatelessWidget {
  const _EmptySlotRow({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(tokens.radius.lg),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(tokens.radius.lg),
        child: Container(
          padding: EdgeInsets.symmetric(
            horizontal: tokens.spacing.lg,
            vertical: tokens.spacing.md,
          ),
          decoration: BoxDecoration(
            border: Border.all(color: colorScheme.outline, width: 1.5),
            borderRadius: BorderRadius.circular(tokens.radius.lg),
          ),
          child: Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'Add a dinner',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
              Icon(Icons.add_rounded, color: colorScheme.primary),
            ],
          ),
        ),
      ),
    );
  }
}

class _FilledSlotRow extends StatelessWidget {
  const _FilledSlotRow({required this.entry, required this.onCooked});

  final MealPlanEntryView entry;
  final VoidCallback onCooked;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    final TextTheme textTheme = Theme.of(context).textTheme;
    final bool cooked = entry.isCooked;

    return Card(
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.md),
        child: Row(
          children: <Widget>[
            // The leading status circle → checkmark swap (AC-PLAN-13 — RN
            // swapped these two `View`s with no transition at all).
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 220),
              transitionBuilder: (Widget child, Animation<double> animation) =>
                  ScaleTransition(scale: animation, child: child),
              child: cooked
                  ? CircleAvatar(
                      key: const ValueKey<String>('cooked'),
                      backgroundColor: colorScheme.primaryContainer,
                      child: Icon(
                        Icons.check_rounded,
                        color: colorScheme.onPrimaryContainer,
                        size: 18,
                      ),
                    )
                  : CircleAvatar(
                      key: const ValueKey<String>('uncooked'),
                      backgroundColor: colorScheme.surfaceContainerHighest,
                      child: Icon(
                        Icons.restaurant_rounded,
                        color: colorScheme.onSurfaceVariant,
                        size: 16,
                      ),
                    ),
            ),
            SizedBox(width: tokens.spacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Text(
                    entry.recipeTitle,
                    overflow: TextOverflow.ellipsis,
                    style: cooked
                        ? textTheme.titleMedium?.copyWith(
                            color: colorScheme.onSurfaceVariant,
                          )
                        : textTheme.titleMedium,
                  ),
                  Text(
                    '${entry.servings} ${entry.servings == 1 ? 'serving' : 'servings'}'
                    '${cooked ? ' · Cooked' : ''}',
                    style: textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            SizedBox(width: tokens.spacing.md),
            // The trailing "Cooked?" pill (a themed `OutlinedButton`, AC-DS-05
            // — never a hand-rolled pill) fades out once cooked, rather than
            // vanishing outright.
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 220),
              transitionBuilder: (Widget child, Animation<double> animation) =>
                  FadeTransition(opacity: animation, child: child),
              child: cooked
                  ? const SizedBox.shrink(key: ValueKey<String>('cooked-gap'))
                  : OutlinedButton(
                      key: const ValueKey<String>('cooked-button'),
                      onPressed: onCooked,
                      child: const Text('Cooked?'),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
