import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'haptics.dart';
import 'tokens.dart';

/// A themed swipe-to-delete row on [Dismissible], which owns the gesture, threshold and exit animation.
/// Adds the danger-tinted reveal background and exactly one [Haptics.mediumImpact] on commit.
class SwipeToDeleteRow extends ConsumerWidget {
  const SwipeToDeleteRow({
    super.key,
    required this.dismissibleKey,
    required this.onDelete,
    required this.child,
    this.direction = DismissDirection.endToStart,
  });

  /// Forwarded to [Dismissible.key]. Must be stable and unique within the
  /// enclosing list (typically the row's id) so Flutter can track it across
  /// list-mutation animations.
  final Key dismissibleKey;

  /// Called once the swipe commits. Callers do the actual delete, ideally with an undo snackbar via
  /// `GleanSnackBar.runUndoable`.
  final VoidCallback onDelete;

  final Widget child;

  /// Defaults to a left swipe revealing a trailing action; overridable for right-to-left rows.
  final DismissDirection direction;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    final AppTokens tokens = context.tokens;

    return Dismissible(
      key: dismissibleKey,
      direction: direction,
      background: _DeleteReveal(
        colorScheme: colorScheme,
        radius: tokens.radius.lg,
      ),
      onDismissed: (DismissDirection _) {
        ref.read(hapticsProvider).mediumImpact();
        onDelete();
      },
      child: child,
    );
  }
}

class _DeleteReveal extends StatelessWidget {
  const _DeleteReveal({required this.colorScheme, required this.radius});

  final ColorScheme colorScheme;
  final double radius;

  @override
  Widget build(BuildContext context) {
    return Container(
      alignment: Alignment.centerRight,
      padding: const EdgeInsets.symmetric(horizontal: 20),
      decoration: BoxDecoration(
        color: colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(radius),
      ),
      child: Icon(
        Icons.delete_outline_rounded,
        color: colorScheme.onErrorContainer,
      ),
    );
  }
}
