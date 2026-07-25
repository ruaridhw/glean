/// The integration seam for showing [OnboardingScreen] at all.
///
/// Wired into `lib/router/router.dart`'s `StatefulShellRoute.indexedStack`
/// (R-04/R-01, .scratch/flutter-port/REMEDIATION.md): the builder there wraps
/// `AppShell(navigationShell: navigationShell)` in
/// `OnboardingGate(child: ...)`, so a first-run user lands on
/// [OnboardingScreen] instead of any tab, and a returning user passes
/// straight through. See `test/router/onboarding_gate_wiring_test.dart` for
/// the proof through the real route table.
///
/// Deliberately placed *inside* the router's widget tree (rather than
/// wrapping `MaterialApp.router` in `lib/app.dart`, which is
/// orchestrator-owned anyway) so [OnboardingScreen] still has a `GoRouter`
/// in its `BuildContext` to navigate with once setup finishes (AC-UX-04 —
/// "ending by pointing at receipt-scan").
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
    // Fail open on both `loading` and `error`: a status-check hiccup must
    // never block the whole app behind a screen that only exists to ask
    // three short questions (AC-UX-04 — "genuinely skippable ... must not
    // become a wall").
    final bool completed = hasCompleted.maybeWhen(
      data: (bool value) => value,
      orElse: () => true,
    );
    return completed ? child : const OnboardingScreen();
  }
}
