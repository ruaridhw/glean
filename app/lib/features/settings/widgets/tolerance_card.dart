import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/design_system/design_system.dart';

import '../settings_presentation.dart';

/// The "purchase tolerance" slider card — settings-only (onboarding doesn't
/// capture this), so it isn't one of the shared controls, but it follows the
/// exact same step/commit haptic split as [IntegerSliderControl] (AC-SET-02,
/// AC-HAP-05): `selectionClick` per 0.1 step while dragging, and
/// [onCommitted] fired once on release.
class ToleranceCard extends ConsumerWidget {
  const ToleranceCard({
    super.key,
    required this.tolerance,
    required this.onChanged,
    required this.onCommitted,
    this.sliderKey,
  });

  final double tolerance;
  final ValueChanged<double> onChanged;
  final ValueChanged<double> onCommitted;
  final Key? sliderKey;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppTokens tokens = context.tokens;
    return Card(
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    'Purchase tolerance',
                    style: Theme.of(context).textTheme.titleMedium,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                GleanBadge(
                  label: '${(tolerance * 100).round()}%',
                  tone: GleanBadgeTone.primary,
                ),
              ],
            ),
            Text(
              getToleranceLabel(tolerance),
              style: Theme.of(context).textTheme.bodySmall,
            ),
            Slider(
              key: sliderKey,
              value: tolerance,
              divisions: 10,
              onChanged: (double raw) {
                final double next = (raw * 10).round() / 10;
                if (next == tolerance) return;
                ref.read(hapticsProvider).selectionClick();
                onChanged(next);
              },
              onChangeEnd: (double raw) => onCommitted((raw * 10).round() / 10),
            ),
          ],
        ),
      ),
    );
  }
}
