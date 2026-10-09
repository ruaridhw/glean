import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

import '../../settings/settings_presentation.dart';
import '../../settings/widgets/dietary_flags_control.dart';
import '../../settings/widgets/integer_slider_control.dart';
import 'onboarding_step_scaffold.dart';

/// Whichever question is current (AC-DS-14 — extracted into its own
/// `const`-constructible class rather than an `OnboardingScreen` builder
/// method, per R-12: a builder method shares its parent's rebuild scope, an
/// extracted class gets its own). Keyed by [step] at the call site so
/// `AnimatedSwitcher` still detects a step change and cross-fades between
/// them.
class OnboardingStepBody extends StatelessWidget {
  const OnboardingStepBody({
    required super.key,
    required this.step,
    required this.dinners,
    required this.servings,
    required this.dietaryFlags,
    required this.onDinnersChanged,
    required this.onServingsChanged,
    required this.onDietaryFlagToggled,
  });

  final int step;
  final int dinners;
  final int servings;
  final Set<String> dietaryFlags;
  final ValueChanged<int> onDinnersChanged;
  final ValueChanged<int> onServingsChanged;
  final void Function(String flag, bool isSelected) onDietaryFlagToggled;

  @override
  Widget build(BuildContext context) {
    switch (step) {
      case 0:
        return OnboardingStepScaffold(
          question: 'How many dinners do you cook at home most weeks?',
          child: _NumberAnswer(
            value: dinners,
            unit: dinners == 1 ? 'dinner a week' : 'dinners a week',
            slider: IntegerSliderControl(
              value: dinners,
              min: SettingsOptionRanges.dinnersPerWeek.min,
              max: SettingsOptionRanges.dinnersPerWeek.max,
              onChanged: onDinnersChanged,
              onCommitted: onDinnersChanged,
            ),
          ),
        );
      case 1:
        return OnboardingStepScaffold(
          question: 'How many people are you usually cooking for?',
          child: _NumberAnswer(
            value: servings,
            unit: servings == 1 ? 'person' : 'people',
            slider: IntegerSliderControl(
              value: servings,
              min: SettingsOptionRanges.defaultServings.min,
              max: SettingsOptionRanges.defaultServings.max,
              onChanged: onServingsChanged,
              onCommitted: onServingsChanged,
            ),
          ),
        );
      case 2:
        return OnboardingStepScaffold(
          question: 'Any dietary preferences we should know about?',
          subtitle: 'Optional — skip this if none apply.',
          child: DietaryFlagsControl(
            selected: dietaryFlags,
            onToggle: onDietaryFlagToggled,
          ),
        );
      default:
        return const OnboardingStepScaffold(
          question: 'Stock your pantry',
          subtitle:
              'Scan a shop receipt and Glean adds what you bought, so meal '
              'plans start from what you already have.',
          child: Center(child: Icon(Icons.receipt_long_rounded, size: 72)),
        );
    }
  }
}

/// A slider step's current answer, large enough to read at a glance while
/// dragging (Settings shows the same value in its card's badge).
class _NumberAnswer extends StatelessWidget {
  const _NumberAnswer({
    required this.value,
    required this.unit,
    required this.slider,
  });

  final int value;
  final String unit;
  final Widget slider;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ThemeData theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Text(
          '$value',
          key: const ValueKey<String>('onboarding.selectedValue'),
          textAlign: TextAlign.center,
          style: theme.textTheme.displayMedium?.copyWith(
            color: theme.colorScheme.primary,
          ),
        ),
        Text(
          unit,
          textAlign: TextAlign.center,
          style: theme.textTheme.titleMedium,
        ),
        // Room for the slider's value bubble, which rises above the thumb
        // while dragging.
        SizedBox(height: tokens.spacing.xxl),
        slider,
      ],
    );
  }
}
