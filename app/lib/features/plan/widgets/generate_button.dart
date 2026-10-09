/// The Generate button: disabled the instant a generation is pending
/// (AC-PLAN-09) — RN's version wasn't, so a double-tap fired two mutations
/// that each computed the empty-slot count from the same stale state and
/// overfilled past `meals_per_week`. Plan-full is still checked up front so
/// tapping it does nothing worse than tell you so.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/auth/auth_controller.dart'
    show aiFeaturesAvailableProvider;
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/plan_providers.dart';
import 'package:glean/data/providers/user_config_providers.dart';
import 'package:glean/design_system/design_system.dart';

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
    final bool pending = ref.watch(generateWeekControllerProvider).isLoading;
    final bool ready = remainingAsync.hasValue && configAsync.hasValue;
    // R-08/AC-AUTH-04: generation calls the AI backend, so an expired
    // session disables it — the [SignedOutBanner] mounted above every tab is
    // what explains why.
    final bool aiAvailable = ref.watch(aiFeaturesAvailableProvider);

    return FilledButton.icon(
      onPressed: pending || !ready || !aiAvailable
          ? null
          : () => _onPressed(
              context,
              ref,
              remaining: remainingAsync.requireValue,
              servings: configAsync.requireValue.preferredServings,
            ),
      icon: pending
          ? SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: Theme.of(context).colorScheme.onPrimary,
              ),
            )
          : const Icon(Icons.auto_awesome_rounded),
      label: Text(pending ? 'Generating' : 'Generate'),
    );
  }

  Future<void> _onPressed(
    BuildContext context,
    WidgetRef ref, {
    required int remaining,
    required int servings,
  }) async {
    if (remaining <= 0) {
      GleanSnackBar.show(context, "This week's plan is full.");
      return;
    }
    ref.read(hapticsProvider).mediumImpact();
    await ref
        .read(generateWeekControllerProvider.notifier)
        .generate(weekStart: weekStart, slots: remaining, servings: servings);
  }
}
