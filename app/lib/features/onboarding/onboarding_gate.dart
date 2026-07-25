/// The integration seam for showing [OnboardingScreen] at all.
///
/// **Required follow-up for the Router module**: nothing in `lib/router/**`
/// currently mounts this. Wrap the shell it builds — in
/// `lib/router/router.dart`'s `StatefulShellRoute.indexedStack`, that's
/// `AppShell(navigationShell: navigationShell)` — as
/// `OnboardingGate(child: AppShell(navigationShell: navigationShell))`. That
/// is the entire integration: this widget already does the rest (checking
/// first-run status, showing/hiding itself, and — once finished — getting
/// out of the way so `child` renders). Until that one-line change lands,
/// [OnboardingScreen] is fully built and tested in isolation
/// (`test/features/onboarding/`) but unreachable through real navigation.
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
