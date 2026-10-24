import 'package:flutter/material.dart';

import '../onboarding_page.dart';
import 'onboarding_basics_page.dart';
import 'onboarding_step_scaffold.dart';
import 'onboarding_taste_page.dart';

/// Whichever page is current, as its own widget for its own rebuild scope. Keyed by page at the call site so
/// `AnimatedSwitcher` detects the change and cross-fades.
class OnboardingStepBody extends StatelessWidget {
  const OnboardingStepBody({
    required super.key,
    required this.page,
    required this.dinners,
    required this.servings,
    required this.dietaryFlags,
    required this.onDinnersChanged,
    required this.onServingsChanged,
    required this.onDietaryFlagToggled,
    required this.onTasteConfirmed,
    required this.onBack,
  });

  final OnboardingPage page;
  final int dinners;
  final int servings;
  final Set<String> dietaryFlags;
  final ValueChanged<int> onDinnersChanged;
  final ValueChanged<int> onServingsChanged;
  final void Function(String flag, bool isSelected) onDietaryFlagToggled;

  /// The household confirmed the interview's summary and its profile was saved. The interview keeps its own
  /// per-turn actions and its own footer; it only needs to say when it is finished.
  final VoidCallback onTasteConfirmed;

  /// One page back, used by the interview, which has no footer of its own.
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    switch (page) {
      case OnboardingPage.basics:
        return OnboardingBasicsPage(
          dinners: dinners,
          servings: servings,
          dietaryFlags: dietaryFlags,
          onDinnersChanged: onDinnersChanged,
          onServingsChanged: onServingsChanged,
          onDietaryFlagToggled: onDietaryFlagToggled,
        );
      case OnboardingPage.tastes:
        return OnboardingTastePage(
          onConfirmed: onTasteConfirmed,
          onBack: onBack,
        );
      case OnboardingPage.pantry:
        // The scaffold centres itself while it fits and scrolls when it does
        // not, which is what keeps this page usable at large text sizes.
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
