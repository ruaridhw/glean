import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

import '../onboarding_screen.dart';

/// "Back"/"Next" on every step but the last, "Scan a receipt"/"I'll do
/// this later" on it (AC-DS-14, R-12 — extracted into its own
/// `const`-constructible class rather than an `OnboardingScreen` builder
/// method, for its own rebuild scope).
class OnboardingFooter extends StatelessWidget {
  const OnboardingFooter({
    super.key,
    required this.step,
    required this.onBack,
    required this.onNext,
    required this.onScanReceipt,
    required this.onFinishLater,
  });

  final int step;
  final VoidCallback onBack;
  final VoidCallback onNext;
  final VoidCallback onScanReceipt;
  final VoidCallback onFinishLater;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final bool isLastStep = step == OnboardingScreen.stepCount - 1;
    if (!isLastStep) {
      return Row(
        children: <Widget>[
          if (step > 0)
            OutlinedButton(onPressed: onBack, child: const Text('Back')),
          const Spacer(),
          FilledButton(onPressed: onNext, child: const Text('Next')),
        ],
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        FilledButton(
          onPressed: onScanReceipt,
          child: const Text('Scan a receipt'),
        ),
        SizedBox(height: tokens.spacing.sm),
        TextButton(
          onPressed: onFinishLater,
          child: const Text("I'll do this later"),
        ),
      ],
    );
  }
}
