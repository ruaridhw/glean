import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

import 'integer_slider_control.dart';

/// Settings' card chrome around the shared [IntegerSliderControl] — title
/// plus a live value badge. Kept separate from the control itself so
/// onboarding (which wants a bigger question-style heading, not a card) can
/// reuse the bare control without this wrapper.
class PreferenceSliderCard extends StatelessWidget {
  const PreferenceSliderCard({
    super.key,
    required this.title,
    required this.value,
    required this.min,
    required this.max,
    required this.onChanged,
    required this.onCommitted,
    this.sliderKey,
  });

  final String title;
  final int value;
  final int min;
  final int max;
  final ValueChanged<int> onChanged;
  final ValueChanged<int> onCommitted;
  final Key? sliderKey;

  @override
  Widget build(BuildContext context) {
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
                    title,
                    style: Theme.of(context).textTheme.titleMedium,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                GleanBadge(label: '$value', tone: GleanBadgeTone.primary),
              ],
            ),
            IntegerSliderControl(
              value: value,
              min: min,
              max: max,
              onChanged: onChanged,
              onCommitted: onCommitted,
              sliderKey: sliderKey,
            ),
          ],
        ),
      ),
    );
  }
}
