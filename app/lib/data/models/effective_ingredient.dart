// The rules a catalogue item really has for this household, after overrides: what every reader of tracking mode,
// stock unit, shelf life or store section uses. Built only by `CatalogueRepository.effectiveIngredient`.
class EffectiveIngredient {
  const EffectiveIngredient({
    required this.id,
    required this.name,
    required this.groupId,
    required this.form,
    required this.trackingMode,
    required this.stockUnit,
    required this.unopenedShelfLifeDays,
    required this.onceOpenedShelfLifeDays,
    required this.section,
  });

  /// The surviving item's id, which differs from the id asked for when that one was merged into another.
  final String id;
  final String name;
  final String groupId;
  final String form;

  /// `counted`, `presence` or `perishable`.
  final String trackingMode;

  /// `g`, `ml` or `count` for a counted ingredient; null otherwise.
  final String? stockUnit;
  final int unopenedShelfLifeDays;

  /// Null where an opened pack has no limit.
  final int? onceOpenedShelfLifeDays;
  final String section;
}
