import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// Where the household is in first-run setup: one slot per page, with the
/// taste interview's slot reserved (dashed, inert) until V13 adds it.
///
/// The indicator is display-only. It deliberately has no tap targets: the flow
/// is linear and skippable, so jumping to a page directly is not a thing the
/// user can do.
class OnboardingProgress extends StatelessWidget {
  const OnboardingProgress({required this.currentSlot, super.key});

  static const int basicsSlot = 0;
  static const int interviewSlot = 1;
  static const int pantrySlot = 2;
  static const List<String> labels = <String>['Basics', 'Taste', 'Pantry'];

  final int currentSlot;

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
                isReserved: slot == interviewSlot,
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
    required this.isReserved,
  });

  final int slot;
  final String label;
  final bool isCurrent;
  final bool isReserved;

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
    final Color numberBackground = isCurrent
        ? colors.primary
        : colors.surfaceContainerHighest;
    final Color numberForeground = isCurrent
        ? colors.onPrimary
        : colors.onSurfaceVariant;

    final Widget pill = Container(
      padding: EdgeInsets.symmetric(horizontal: tokens.spacing.sm, vertical: 6),
      decoration: isReserved
          ? null
          : BoxDecoration(
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
              border: isCurrent
                  ? null
                  : Border.all(
                      color: isReserved
                          ? colors.outlineVariant
                          : colors.outline,
                    ),
            ),
            child: Text(
              '${slot + 1}',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                fontSize: 10,
                letterSpacing: 0,
                color: numberForeground,
              ),
            ),
          ),
          SizedBox(width: tokens.spacing.xs + 2),
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

    final String semanticsLabel =
        'Step ${slot + 1} of ${OnboardingProgress.labels.length}: $label'
        '${isReserved ? ', coming later' : ''}';

    return Semantics(
      key: ValueKey<String>('onboarding.step.$slot'),
      label: semanticsLabel,
      selected: isCurrent,
      child: ExcludeSemantics(
        child: isReserved
            ? CustomPaint(
                painter: _DashedPillBorder(color: colors.outlineVariant),
                child: pill,
              )
            : pill,
      ),
    );
  }
}

/// A dashed stadium outline, used only for the reserved interview slot. Flutter
/// has no dashed border, and pulling in a package for one pill is not worth it.
class _DashedPillBorder extends CustomPainter {
  const _DashedPillBorder({required this.color});

  final Color color;

  static const double _dash = 4;
  static const double _gap = 3;

  @override
  void paint(Canvas canvas, Size size) {
    final Path outline = Path()
      ..addRRect(
        RRect.fromRectAndRadius(
          Offset.zero & size,
          Radius.circular(size.height / 2),
        ),
      );
    final Paint paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    for (final metric in outline.computeMetrics()) {
      double start = 0;
      while (start < metric.length) {
        final double end = math.min(start + _dash, metric.length);
        canvas.drawPath(metric.extractPath(start, end), paint);
        start = end + _gap;
      }
    }
  }

  @override
  bool shouldRepaint(_DashedPillBorder oldDelegate) =>
      oldDelegate.color != color;
}
