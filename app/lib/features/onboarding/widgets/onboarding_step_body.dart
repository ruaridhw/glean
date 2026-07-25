import 'package:flutter/material.dart';

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
          child: IntegerSliderControl(
            value: dinners,
            min: SettingsOptionRanges.dinnersPerWeek.min,
            max: SettingsOptionRanges.dinnersPerWeek.max,
            onChanged: onDinnersChanged,
            onCommitted: onDinnersChanged,
          ),
        );
      case 1:
        return OnboardingStepScaffold(
          question: 'How many people are you usually cooking for?',
          child: IntegerSliderControl(
            value: servings,
            min: SettingsOptionRanges.defaultServings.min,
            max: SettingsOptionRanges.defaultServings.max,
            onChanged: onServingsChanged,
            onCommitted: onServingsChanged,
          ),
        );
      default:
        return OnboardingStepScaffold(
          question: 'Any dietary preferences we should know about?',
          subtitle: 'Optional — skip this if none apply.',
          child: DietaryFlagsControl(
            selected: dietaryFlags,
            onToggle: onDietaryFlagToggled,
          ),
        );
    }
  }
}
