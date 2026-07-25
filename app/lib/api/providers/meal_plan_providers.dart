import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/meal_plan.dart';
import 'api_providers.dart';

/// Command controller for `POST /meal-plan`. Returns an ephemeral list of
/// suggested recipes (AC-DATA-06) for the Plan screen to review; nothing is
/// written to the meal plan table until the user accepts a suggestion via a
/// DATA mutation.
///
/// Callers must build [MealPlanRequest] with real `foodGroups`/
/// `foodGroupCoverage` (AC-PLAN-08) — this controller does not default them,
/// unlike the RN client, which hardcoded `food_group_coverage: {}` and made
/// the backend's food-group-balancing prompt rule permanently inert.
class GenerateMealPlanController extends AsyncNotifier<MealPlanResponse?> {
  @override
  FutureOr<MealPlanResponse?> build() => null;

  /// See `ScanReceiptController.scan`'s doc comment
  /// (`lib/api/providers/receipts_providers.dart`) for why the
  /// [Ref.keepAlive] hold-and-release is here (FINDINGS.md F-15). Callers no
  /// longer need their own keep-alive workaround for this reason — see
  /// `lib/features/plan/providers/generate_week_controller.dart`.
  Future<void> generate(MealPlanRequest request) async {
    state = const AsyncLoading();
    final keepAliveLink = ref.keepAlive();
    try {
      final client = ref.read(apiClientProvider);
      state = await AsyncValue.guard(() => client.generateMealPlan(request));
    } finally {
      keepAliveLink.close();
    }
  }
}

final AsyncNotifierProvider<GenerateMealPlanController, MealPlanResponse?>
generateMealPlanControllerProvider = AsyncNotifierProvider.autoDispose(
  GenerateMealPlanController.new,
);
