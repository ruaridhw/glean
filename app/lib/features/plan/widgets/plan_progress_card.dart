/// The "Dinner progress" card: an animated ring plus the "N left to plan"
/// hint (FLUTTER_MIGRATION.md §7 — RN's SVG ring was fully static, so it
/// teleported from 0/5 to 5/5 the instant a generation completed,
/// AC-PLAN-12).
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

import '../presentation.dart';

class PlanProgressCard extends StatelessWidget {
  const PlanProgressCard({
    super.key,
    required this.planned,
    required this.target,
    required this.remaining,
  });

  /// Total entries this week, cooked or not — a cooked meal still counts
  /// towards this figure (it keeps the "you did it" satisfaction loop
  /// alive, AC-PLAN-03's other half) even though it no longer counts
  /// towards [remaining].
  final int planned;
  final int target;

  /// Per-week remaining capacity (already excludes cooked entries,
  /// AC-PLAN-03/04) — see `planHint`'s doc comment for why this must be
  /// passed in rather than re-derived from [planned]/[target] here.
  final int remaining;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Card(
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.lg),
        child: Row(
          children: <Widget>[
            _PlanProgressRing(planned: planned, target: target),
            SizedBox(width: tokens.spacing.lg),
            Expanded(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'Dinner progress',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  Text(
                    planHint(remaining),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PlanProgressRing extends StatelessWidget {
  const _PlanProgressRing({required this.planned, required this.target});

  final int planned;
  final int target;

  static const double _size = 56;
  static const double _strokeWidth = 6;

  @override
  Widget build(BuildContext context) {
    final double fraction = target > 0
        ? (planned / target).clamp(0.0, 1.0)
        : 0.0;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;

    return TweenAnimationBuilder<double>(
      // `begin: 0` only matters for the very first frame — see
      // `skeleton.dart`'s identical note. On a later rebuild where
      // `fraction` has changed, TweenAnimationBuilder animates from
      // whichever value it last rendered towards the new `end`, which is
      // exactly what turns a 0/5 -> 5/5 jump after generation into a
      // smooth sweep instead of a teleport (AC-PLAN-12).
      tween: Tween<double>(begin: 0, end: fraction),
      duration: const Duration(milliseconds: 600),
      curve: Curves.easeOutCubic,
      builder: (BuildContext context, double value, Widget? child) {
        return SizedBox(
          width: _size,
          height: _size,
          child: CustomPaint(
            key: const ValueKey<String>('plan-progress-ring-paint'),
            painter: PlanProgressRingPainter(
              fraction: value,
              trackColor: colorScheme.surfaceContainerHighest,
              progressColor: colorScheme.primary,
              strokeWidth: _strokeWidth,
            ),
            child: Center(
              child: Text(
                '$planned/$target',
                style: Theme.of(
                  context,
                ).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w800),
              ),
            ),
          ),
        );
      },
    );
  }
}

/// Public (not `_`-prefixed) so a widget test can find the [CustomPaint] by
/// its key and read [fraction] mid-animation to prove the ring is actually
/// sweeping rather than snapping straight to the final value.
class PlanProgressRingPainter extends CustomPainter {
  const PlanProgressRingPainter({
    required this.fraction,
    required this.trackColor,
    required this.progressColor,
    required this.strokeWidth,
  });

  final double fraction;
  final Color trackColor;
  final Color progressColor;
  final double strokeWidth;

  @override
  void paint(Canvas canvas, Size size) {
    final Offset center = Offset(size.width / 2, size.height / 2);
    final double radius = (size.shortestSide - strokeWidth) / 2;

    final Paint track = Paint()
      ..color = trackColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth;
    canvas.drawCircle(center, radius, track);

    if (fraction <= 0) return;
    final Paint progress = Paint()
      ..color = progressColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;
    const double startAngle = -math.pi / 2;
    final double sweepAngle = 2 * math.pi * fraction;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      sweepAngle,
      false,
      progress,
    );
  }

  @override
  bool shouldRepaint(covariant PlanProgressRingPainter oldDelegate) =>
      oldDelegate.fraction != fraction ||
      oldDelegate.trackColor != trackColor ||
      oldDelegate.progressColor != progressColor ||
      oldDelegate.strokeWidth != strokeWidth;
}
