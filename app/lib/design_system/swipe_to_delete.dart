import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'haptics.dart';
import 'tokens.dart';

/// A themed swipe-to-delete row built on the built-in [Dismissible]
/// (AC-DS-09).
///
/// The RN app implemented this with `swipe-delete-row.tsx` — ~100 lines of
/// `PanResponder` + `Animated` — plus a hand-written distance/velocity
/// threshold in `swipe-action.ts` (`shouldRunSwipeAction`). None of that
/// exists here: [Dismissible] already owns the drag gesture, the
/// distance/fling threshold, and the exit/resize animation. This wrapper
/// adds only what's specific to Glean:
///
/// - the themed "revealed" background (danger-tinted, trailing trash icon),
///   coloured from [Theme.of(context)] rather than a local constant;
/// - firing exactly **one** [Haptics.mediumImpact] on commit (AC-HAP-03 — the
///   RN app buzzed twice here because both the row and a separate delete
///   `IconButton` fired their own haptic; there is only one delete affordance
///   here, and only one haptic call site).
///
/// Callers only ever get a callback ([onDelete]) — there is no
/// threshold/gesture maths for a caller to get wrong.
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

  /// Called once the swipe commits. Callers do the actual delete (and should
  /// show an undo snackbar via `GleanSnackBar.showUndo` — AC-UX-02); this
  /// widget's only added responsibility is the single haptic.
  final VoidCallback onDelete;

  final Widget child;

  /// RN only ever swiped one way (left, revealing a trailing action) — kept
  /// as the default, but overridable for a row that reads right-to-left.
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
