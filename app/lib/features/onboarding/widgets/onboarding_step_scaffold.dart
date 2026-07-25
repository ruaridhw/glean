import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// Shared chrome for one onboarding step: a question-style heading, an
/// optional subtitle, and whichever control answers it. Kept separate from
/// [OnboardingScreen] so the heading style is consistent across steps
/// without repeating it at each call site.
class OnboardingStepScaffold extends StatelessWidget {
  const OnboardingStepScaffold({
    super.key,
    required this.question,
    required this.child,
    this.subtitle,
  });

  final String question;
  final String? subtitle;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Padding(
      padding: EdgeInsets.symmetric(horizontal: tokens.spacing.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text(question, style: Theme.of(context).textTheme.headlineLarge),
          if (subtitle != null) ...<Widget>[
            SizedBox(height: tokens.spacing.sm),
            Text(subtitle!, style: Theme.of(context).textTheme.bodyMedium),
          ],
          SizedBox(height: tokens.spacing.xl),
          child,
        ],
      ),
    );
  }
}
