import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// Where the household is in first-run setup: one slot per page, with the
/// taste interview's slot reserved (dashed, inert) until V13 adds it.
///
/// The indicator is display-only. It deliberately has no tap targets: the flow
/// is linear and skippable, so jumping to a page directly is not a thing the
/// user can do.
class OnboardingProgress extends StatelessWidget {
  const OnboardingProgress({
    required this.currentSlot,
    this.completedSlots = const <int>{},
    this.skippedSlots = const <int>{},
    super.key,
  });

  static const int basicsSlot = 0;
  static const int tastesSlot = 1;
  static const int pantrySlot = 2;
  static const List<String> labels = <String>['Basics', 'Taste', 'Pantry'];

  final int currentSlot;

  /// Slots the household has moved past by answering them, and by skipping
  /// them. Kept apart so the indicator never claims an answer that was not
  /// given.
  final Set<int> completedSlots;
  final Set<int> skippedSlots;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Semantics(
      container: true,
      label: 'Setup progress',
      child: Row(
        children: <Widget>[
          for (int slot = 0; slot < labels.length; slot++) ...<Widget>[
            if (slot > 0) SizedBox(width: tokens.spacing.sm),
            Expanded(
              child: _StepSlot(
                slot: slot,
                label: labels[slot],
                isCurrent: slot == currentSlot,
                isCompleted: completedSlots.contains(slot),
                isSkipped: skippedSlots.contains(slot),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _StepSlot extends StatelessWidget {
  const _StepSlot({
    required this.slot,
    required this.label,
    required this.isCurrent,
    required this.isCompleted,
    required this.isSkipped,
  });

  final int slot;
  final String label;
  final bool isCurrent;
  final bool isCompleted;
  final bool isSkipped;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ColorScheme colors = Theme.of(context).colorScheme;
    final TextStyle? labelStyle = Theme.of(context).textTheme.labelLarge
        ?.copyWith(
          fontWeight: FontWeight.w700,
          color: isCurrent
              ? colors.onPrimaryContainer
              : colors.onSurfaceVariant,
        );
    final Color numberBackground = isCurrent || isCompleted
        ? colors.primary
        : colors.surfaceContainerHighest;
    final Color numberForeground = isCurrent || isCompleted
        ? colors.onPrimary
        : colors.onSurfaceVariant;
    final Widget mark = switch ((isCompleted, isSkipped)) {
      (true, _) => Icon(Icons.check_rounded, size: 12, color: colors.onPrimary),
      (_, true) => Icon(
        Icons.remove_rounded,
        size: 12,
        color: colors.onSurfaceVariant,
      ),
      _ => Text(
        '${slot + 1}',
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
          fontSize: 10,
          letterSpacing: 0,
          color: numberForeground,
        ),
      ),
    };

    final Widget pill = Container(
      padding: EdgeInsets.symmetric(
        horizontal: tokens.spacing.sm,
        vertical: tokens.spacing.xs,
      ),
      decoration: BoxDecoration(
        color: isCurrent
            ? colors.primaryContainer
            : colors.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(tokens.radius.pill),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Container(
            width: 16,
            height: 16,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: numberBackground,
              shape: BoxShape.circle,
              border: isCurrent || isCompleted
                  ? null
                  : Border.all(color: colors.outline),
            ),
            child: mark,
          ),
          SizedBox(width: tokens.spacing.sm),
          Flexible(
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: labelStyle,
            ),
          ),
        ],
      ),
    );

    final String passedState = isCompleted
        ? ', completed'
        : isSkipped
        ? ', skipped'
        : '';
    final String semanticsLabel =
        'Step ${slot + 1} of ${OnboardingProgress.labels.length}: '
        '$label$passedState';

    return Semantics(
      key: ValueKey<String>('onboarding.step.$slot'),
      label: semanticsLabel,
      selected: isCurrent,
      child: ExcludeSemantics(child: pill),
    );
  }
}
