/// The Generate button: its tap opens the full-screen review immediately, so the working state and progress
/// lines live on that screen rather than as a spinner here. Plan-full is still checked up front so tapping it
/// just says so, and a run already in flight is reopened rather than duplicated.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/auth/auth_controller.dart'
    show aiFeaturesAvailableProvider;
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/plan_providers.dart';
import 'package:glean/data/providers/user_config_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:go_router/go_router.dart';

import '../providers/generate_week_controller.dart';

class PlanGenerateButton extends ConsumerWidget {
  const PlanGenerateButton({super.key, required this.weekStart});

  final DateTime weekStart;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<int> remainingAsync = ref.watch(
      planWeekRemainingCapacityProvider(weekStart),
    );
    final AsyncValue<UserConfigView> configAsync = ref.watch(
      userConfigProvider,
    );
    final bool ready = remainingAsync.hasValue && configAsync.hasValue;
    // Generation calls the AI backend, so an expired session disables it; the [SignedOutBanner] above every tab
    // explains why.
    final bool aiAvailable = ref.watch(aiFeaturesAvailableProvider);

    return FilledButton.icon(
      onPressed: !ready || !aiAvailable
          ? null
          : () => _onPressed(
              context,
              ref,
              remaining: remainingAsync.requireValue,
              servings: configAsync.requireValue.preferredServings,
            ),
      icon: const Icon(Icons.auto_awesome_rounded),
      label: const Text('Generate'),
    );
  }

  void _onPressed(
    BuildContext context,
    WidgetRef ref, {
    required int remaining,
    required int servings,
  }) {
    if (remaining <= 0) {
      GleanSnackBar.show(context, "This week's plan is full.");
      return;
    }
    ref.read(hapticsProvider).mediumImpact();
    if (ref.read(generateWeekControllerProvider).phase !=
        GenerateProposalPhase.working) {
      // Starts synchronously into its working state, so the screen's first frame is the progress face.
      unawaited(
        ref
            .read(generateWeekControllerProvider.notifier)
            .generate(
              weekStart: weekStart,
              slots: remaining,
              servings: servings,
            ),
      );
    }
    context.pushNamed(AppRoutes.planProposal.name);
  }
}
