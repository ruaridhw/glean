/// The integration seam for showing [OnboardingScreen]. Wrapped around `AppShell` in the router's tab-shell
/// builder, so a first-run user lands on [OnboardingScreen] instead of any tab and a returning user passes
/// straight through. It sits inside the router's widget tree so [OnboardingScreen] has a `GoRouter` in its
/// `BuildContext` to navigate with once setup finishes.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'onboarding_screen.dart';
import 'providers/onboarding_status.dart';

class OnboardingGate extends ConsumerWidget {
  const OnboardingGate({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<bool> hasCompleted = ref.watch(
      hasCompletedOnboardingProvider,
    );
    // Fail open on both `loading` and `error`: a status-check hiccup must never block the whole app behind a
    // screen that only asks three short questions.
    final bool completed = hasCompleted.maybeWhen(
      data: (bool value) => value,
      orElse: () => true,
    );
    return completed ? child : const OnboardingScreen();
  }
}
