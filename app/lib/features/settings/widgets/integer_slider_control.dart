import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/design_system/design_system.dart';

/// A controlled, whole-number stepping slider shared by Settings and the
/// first-run onboarding flow (FLUTTER_MIGRATION.md §6 — "reuse the same
/// controls as Settings rather than duplicating them").
///
/// Two behaviours are load-bearing here, both from AC-SET-02/AC-HAP-05:
/// - Every step the thumb passes through while dragging fires exactly one
///   `selectionClick` (compared against the *previous* value, so holding
///   still mid-drag never re-fires).
/// - [onCommitted] — the only place a caller should persist anything — is
///   called once, on release ([Slider.onChangeEnd]), never per drag frame.
///   This is the direct fix for the RN sliders' `onValueChange` writing
///   state (and re-rendering) on every drag frame with no
///   `onSlidingComplete`.
///
/// Deliberately stateless about the *committed* value — the caller
/// (Settings/onboarding) owns that, so switching away and back always shows
/// exactly what was last persisted, never a separate in-flight copy.
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
