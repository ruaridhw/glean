// Week-scoped plan reads for the current user.
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/meal_plan_entry_view.dart';
import 'database_providers.dart';
import 'repository_providers.dart';
import 'user_config_providers.dart';

/// Entries in the week starting [weekStart] (a Monday, see `startOfWeek`), including cooked entries.
/// Callers key this `.family` by the week they're paginated to.
final planWeekProvider =
    StreamProvider.family<List<MealPlanEntryView>, DateTime>((ref, weekStart) {
      final userId = ref.watch(currentUserIdProvider);
      return ref
          .watch(planRepositoryProvider)
          .watchWeek(userId: userId, weekStart: weekStart);
    });

/// How many more meals can be added to the week starting [weekStart]: derived from [planWeekProvider] and
/// `mealsPerWeek`, so it updates the instant either changes.
final planWeekRemainingCapacityProvider =
    Provider.family<AsyncValue<int>, DateTime>((ref, weekStart) {
      final entries = ref.watch(planWeekProvider(weekStart));
      final config = ref.watch(userConfigProvider);

      if (entries.isLoading || config.isLoading) {
        return const AsyncValue<int>.loading();
      }
      if (entries.hasError) {
        return AsyncValue<int>.error(entries.error!, entries.stackTrace!);
      }
      if (config.hasError) {
        return AsyncValue<int>.error(config.error!, config.stackTrace!);
      }

      final int uncooked = entries.requireValue
          .where((e) => !e.isCooked)
          .length;
      final int remaining = config.requireValue.mealsPerWeek - uncooked;
      return AsyncValue<int>.data(remaining > 0 ? remaining : 0);
    });
