import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

import '../onboarding_page.dart';

/// The actions for one first-run page. The basics page offers Continue plus a
/// page-scoped Skip; the pantry page keeps its two exits and gains the Back
/// into the basics page.
class OnboardingFooter extends StatelessWidget {
  const OnboardingFooter({
    super.key,
    required this.page,
    required this.onBack,
    required this.onContinue,
    required this.onSkipBasics,
    required this.onScanReceipt,
    required this.onFinishLater,
  });

  final OnboardingPage page;
  final VoidCallback onBack;
  final VoidCallback onContinue;
  final VoidCallback onSkipBasics;
  final VoidCallback onScanReceipt;
  final VoidCallback onFinishLater;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    if (page == OnboardingPage.basics) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          FilledButton(onPressed: onContinue, child: const Text('Continue')),
          SizedBox(height: tokens.spacing.xs),
          TextButton(
            onPressed: onSkipBasics,
            child: const Text('Skip this page'),
          ),
        ],
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Row(
          children: <Widget>[
            OutlinedButton(onPressed: onBack, child: const Text('Back')),
            SizedBox(width: tokens.spacing.md),
            Expanded(
              child: FilledButton(
                onPressed: onScanReceipt,
                child: const Text('Scan a receipt'),
              ),
            ),
          ],
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
