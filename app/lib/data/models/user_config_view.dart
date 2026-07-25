// Mirrors `UserConfig` in `mobile/src/types/index.ts` and the
// `USER_CONFIG_DEFAULTS` fallback in `mobile/src/db/schema.ts` — the
// settings that steer meal-plan generation (dinners/week, servings,
// dietary flags, active-time cap) plus the "no row yet" defaults used
// before a user has ever saved settings.
class UserConfigView {
  const UserConfigView({
    required this.id,
    required this.purchaseTolerance,
    required this.preferredServings,
    required this.mealsPerWeek,
    required this.dietaryFlags,
    required this.maxActiveTimeMins,
  });

  factory UserConfigView.defaults(String id) => UserConfigView(
    id: id,
    purchaseTolerance: defaultPurchaseTolerance,
    preferredServings: defaultPreferredServings,
    mealsPerWeek: defaultMealsPerWeek,
    dietaryFlags: const [],
    maxActiveTimeMins: null,
  );

  static const double defaultPurchaseTolerance = 0.5;
  static const int defaultPreferredServings = 2;
  static const int defaultMealsPerWeek = 5;

  // The Cognito user sub (UUID).
  final String id;
  final double purchaseTolerance;
  final int preferredServings;
  final int mealsPerWeek;
  final List<String> dietaryFlags;
  final int? maxActiveTimeMins;
}
