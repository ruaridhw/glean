/// API ingredient quantities describe the whole recipe at its advertised
/// yield, not one serving. Unknown/invalid yields retain the legacy one-serving
/// basis; no portion count is inferred from ingredient names or amounts.
double recipeQuantityForServings({
  required double quantity,
  required int servings,
  required int? yieldCount,
}) {
  final basis = yieldCount != null && yieldCount > 0 ? yieldCount : 1;
  return quantity * servings / basis;
}
