/// The Plan tab: a week-scoped dinner plan (AC-PLAN-01/02) replacing RN's
/// dateless "This Week", which never filtered on `planned_date`, let cooked
/// meals occupy slots forever, and gated capacity on a *lifetime* entry
/// count that eventually blocked every add, permanently
/// (FLUTTER_MIGRATION.md §6 Plan).
///
/// See `providers/generate_week_controller.dart` for generation,
/// `actions.dart` for the cooked/delete mutations, and
/// `presentation.dart`/`compression.dart`/`food_groups.dart` for the ported
/// pure logic this screen renders.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/pantry_providers.dart';
import 'package:glean/data/providers/plan_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/providers/user_config_providers.dart';
import 'package:glean/data/providers/viewed_plan_week.dart';
import 'package:glean/data/providers/clock_provider.dart';
import 'package:glean/data/util/week.dart';
import 'package:glean/design_system/design_system.dart';

import 'actions.dart';
import 'presentation.dart';
import 'providers/generate_week_controller.dart';
import 'widgets/generate_button.dart';
import 'widgets/plan_expiry_banner.dart';
import 'widgets/plan_progress_card.dart';
import 'widgets/plan_skeleton.dart';
import 'widgets/plan_slot_row.dart';
import 'widgets/plan_week_pager.dart';

class PlanScreen extends ConsumerStatefulWidget {
  const PlanScreen({super.key});

  @override
  ConsumerState<PlanScreen> createState() => _PlanScreenState();
}

class _PlanScreenState extends ConsumerState<PlanScreen>
    with WidgetsBindingObserver {
  Timer? _weekTimer;
  DateTime? _lastRolloverWeek;
  bool _rolling = false;
  DateTime get _weekStart => ref.read(viewedPlanWeekProvider);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_rollToCurrentWeek());
    _scheduleWeekBoundary();
  }

  @override
  void dispose() {
    _weekTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(_rollToCurrentWeek());
      _scheduleWeekBoundary();
    }
  }

  void _scheduleWeekBoundary() {
    _weekTimer?.cancel();
    final now = ref.read(clockProvider)();
    final week = startOfWeek(now);
    final next = DateTime(week.year, week.month, week.day + 7);
    _weekTimer = Timer(next.difference(now), () {
      unawaited(_rollToCurrentWeek());
      _scheduleWeekBoundary();
    });
  }

  Future<void> _rollToCurrentWeek() async {
    final now = ref.read(clockProvider)();
    final week = startOfWeek(now);
    if (_rolling || _lastRolloverWeek == week) return;
    _rolling = true;
    try {
      await ref
          .read(planRepositoryProvider)
          .rolloverUncookedMeals(
            userId: ref.read(currentUserIdProvider),
            referenceDate: now,
          );
      if (!mounted) return;
      if (_lastRolloverWeek != null && _weekStart == _lastRolloverWeek) {
        ref.read(viewedPlanWeekProvider.notifier).select(week);
      }
      _lastRolloverWeek = week;
    } catch (_) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          GleanSnackBar.show(
            context,
            'Could not roll over your meals. Try again.',
          );
        }
      });
    } finally {
      _rolling = false;
    }
  }

  void _goToPreviousWeek() {
    ref
        .read(viewedPlanWeekProvider.notifier)
        .select(_weekStart.subtract(const Duration(days: 7)));
  }

  void _goToNextWeek() {
    ref
        .read(viewedPlanWeekProvider.notifier)
        .select(_weekStart.add(const Duration(days: 7)));
  }

  @override
  Widget build(BuildContext context) {
    ref.watch(viewedPlanWeekProvider);
    final AppTokens tokens = context.tokens;

    final AsyncValue<List<MealPlanEntryView>> entriesAsync = ref.watch(
      planWeekProvider(_weekStart),
    );
    final AsyncValue<int> remainingAsync = ref.watch(
      planWeekRemainingCapacityProvider(_weekStart),
    );
    final AsyncValue<UserConfigView> configAsync = ref.watch(
      userConfigProvider,
    );
    final AsyncValue<List<PantryItemView>> pantryAsync = ref.watch(
      pantryItemsProvider,
    );

    // Surfaces generation's outcome exactly once per attempt — guarded by
    // `wasPending` so this doesn't fire on the controller's own initial,
    // never-pending `build()` state. Generation completion is the
    // highest-value haptic moment in the app (§7); a failure (a guarded,
    // aborted half-write per AC-PLAN-10) always surfaces here too, never
    // silently.
    ref.listen<AsyncValue<int>>(generateWeekControllerProvider, (
      AsyncValue<int>? previous,
      AsyncValue<int> next,
    ) {
      final bool wasPending = previous?.isLoading ?? false;
      if (!wasPending) return;
      next.when(
        data: (count) {
          ref.read(hapticsProvider).mediumImpact();
          GleanSnackBar.show(
            context,
            count == 0
                ? 'No recipes fit right now. Try again.'
                : 'Week generated · any missing ingredients were added to your shopping list',
          );
        },
        error: (Object error, StackTrace stackTrace) {
          GleanSnackBar.show(context, 'Could not generate meal plan.');
        },
        loading: () {},
      );
    });

    final bool loading = !entriesAsync.hasValue || !configAsync.hasValue;
    final List<MealPlanEntryView> entries =
        entriesAsync.value ?? const <MealPlanEntryView>[];
    final int target =
        configAsync.value?.mealsPerWeek ?? UserConfigView.defaultMealsPerWeek;
    final int remaining = remainingAsync.value ?? 0;
    final List<PlanSlot> slots = buildPlanSlots(entries, target);
    final PlanExpiryNudge? nudge = planExpiryNudge(
      pantryAsync.value ?? const <PantryItemView>[],
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Plan'),
        actions: <Widget>[
          Padding(
            padding: EdgeInsets.only(right: tokens.spacing.md),
            child: PlanGenerateButton(weekStart: _weekStart),
          ),
        ],
      ),
      body: SafeArea(
        child: GleanCrossFade(
          showSkeleton: loading,
          skeleton: const PlanSkeleton(),
          content: ListView(
            padding: EdgeInsets.all(tokens.spacing.lg),
            children: <Widget>[
              PlanWeekPager(
                weekStart: _weekStart,
                onPrevious: _goToPreviousWeek,
                onNext: _goToNextWeek,
              ),
              SizedBox(height: tokens.spacing.md),
              PlanProgressCard(
                planned: entries.where((entry) => !entry.isCooked).length,
                target: target,
                remaining: remaining,
              ),
              SizedBox(height: tokens.spacing.lg),
              Text('Dinners', style: Theme.of(context).textTheme.titleSmall),
              SizedBox(height: tokens.spacing.sm),
              for (final PlanSlot slot in slots)
                Padding(
                  padding: EdgeInsets.only(bottom: tokens.spacing.sm),
                  child: PlanSlotRow(
                    key: ValueKey<String>(slot.key),
                    slot: slot,
                    onEmptyTap: () => onAddDinnerTapped(context, ref),
                  ),
                ),
              if (nudge != null) ...<Widget>[
                SizedBox(height: tokens.spacing.md),
                PlanExpiryBanner(nudge: nudge),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
