import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/design_system/design_system.dart';

import '../settings_presentation.dart';

/// A controlled, whole-number stepping slider shared by Settings and onboarding. Two load-bearing behaviours:
///
/// - Every step the thumb passes through while dragging fires exactly one `selectionClick` (compared against the
///   previous value, so holding still never re-fires).
/// - [onCommitted], the only place a caller should persist, is called once on release ([Slider.onChangeEnd]),
///   never per drag frame.
///
/// Stateless about the committed value: the caller owns it, so switching away and back shows what was last
/// persisted.
class IntegerSliderControl extends ConsumerWidget {
  const IntegerSliderControl({
    super.key,
    required this.value,
    required this.min,
    required this.max,
    required this.onChanged,
    required this.onCommitted,
    this.sliderKey,
  });

  final int value;
  final int min;
  final int max;

  /// Forwarded to the inner [Slider] so widget tests can target a specific
  /// control (e.g. `settings.dinnersSlider`) without relying on tree order.
  final Key? sliderKey;

  /// Called on every step change while dragging. Callers should only update
  /// their own local display state here — never persist (see [onCommitted]).
  final ValueChanged<int> onChanged;

  /// Called once, on release, with the final value. This is the commit
  /// point — the only place a caller should write to storage.
  final ValueChanged<int> onCommitted;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppTokens tokens = context.tokens;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Slider(
          key: sliderKey,
          value: value.toDouble(),
          min: min.toDouble(),
          max: max.toDouble(),
          divisions: max > min ? max - min : null,
          label: '$value',
          onChanged: (double raw) {
            final int next = raw.round();
            if (next == value) return;
            ref.read(hapticsProvider).selectionClick();
            onChanged(next);
          },
          onChangeEnd: (double raw) => onCommitted(raw.round()),
        ),
        Padding(
          padding: EdgeInsets.symmetric(horizontal: tokens.spacing.sm),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: <Widget>[
              Text('$min', style: Theme.of(context).textTheme.bodyMedium),
              Text('$max', style: Theme.of(context).textTheme.bodyMedium),
            ],
          ),
        ),
      ],
    );
  }
}

/// Settings' card chrome around [IntegerSliderControl]: title plus a live value badge. Onboarding uses the bare
/// control under its own question heading instead.
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
    return _SliderCardFrame(
      title: title,
      badge: '$value',
      children: <Widget>[
        IntegerSliderControl(
          value: value,
          min: min,
          max: max,
          onChanged: onChanged,
          onCommitted: onCommitted,
          sliderKey: sliderKey,
        ),
      ],
    );
  }
}

/// The "purchase tolerance" slider card, settings-only (onboarding doesn't capture it). Follows the same
/// step/commit haptic split as [IntegerSliderControl]: `selectionClick` per 0.1 step while dragging,
/// [onCommitted] once on release.
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
    return _SliderCardFrame(
      title: 'Purchase tolerance',
      badge: '${(tolerance * 100).round()}%',
      children: <Widget>[
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
    );
  }
}

class _SliderCardFrame extends StatelessWidget {
  const _SliderCardFrame({
    required this.title,
    required this.badge,
    required this.children,
  });

  final String title;
  final String badge;
  final List<Widget> children;

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
                GleanBadge(label: badge, tone: GleanBadgeTone.primary),
              ],
            ),
            ...children,
          ],
        ),
      ),
    );
  }
}
