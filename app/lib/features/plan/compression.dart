/// Pantry compression for `POST /meal-plan` — ported faithfully from
/// `mobile/src/meal-plan/compress.ts` (FLUTTER_MIGRATION.md's "highest-value
/// logic to port" table). Scores every non-staple, in-stock pantry item by
/// urgency (expiry proximity, time since last use, low quantity) and keeps
/// only the top [defaultTopN], so the LLM request payload stays small
/// regardless of pantry size.
library;

import 'dart:math' as math;

import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/data/models/pantry_item_view.dart';

const int defaultTopN = 15;

/// Scores [item]'s urgency to use up (higher = more urgent). Matches
/// `scorePantryItem` in `compress.ts` exactly:
///  - expiring within 1/3/7 days adds 100/50/20;
///  - days since last use adds up to 30 (capped), or a flat 15 if never
///    used;
///  - a low-but-nonzero quantity (<100 in the item's own unit) adds 10.
double scorePantryItem(PantryItemView item, {DateTime? now}) {
  final DateTime effectiveNow = now ?? DateTime.now();
  double score = 0;

  final DateTime? expiry = item.expiryDate;
  if (expiry != null) {
    final double daysUntilExpiry =
        expiry.difference(effectiveNow).inMilliseconds /
        Duration.millisecondsPerDay;
    if (daysUntilExpiry <= 1) {
      score += 100;
    } else if (daysUntilExpiry <= 3) {
      score += 50;
    } else if (daysUntilExpiry <= 7) {
      score += 20;
    }
  }

  final DateTime? lastUsed = item.lastUsedAt;
  if (lastUsed != null) {
    final double daysSinceUsed =
        effectiveNow.difference(lastUsed).inMilliseconds /
        Duration.millisecondsPerDay;
    score += math.min(30, daysSinceUsed);
  } else {
    score += 15;
  }

  if (item.quantity > 0 && item.quantity < 100) score += 10;

  return score;
}

/// Compresses [items] to the top [topN] by urgency, excluding staples
/// (assumed always available) and zero-quantity rows. This is what feeds
/// `MealPlanRequest.pantry` — see `providers/generate_week_controller.dart`.
List<CompressedPantryItem> compressPantry(
  List<PantryItemView> items, {
  int topN = defaultTopN,
  DateTime? now,
}) {
  final DateTime effectiveNow = now ?? DateTime.now();
  final List<(PantryItemView, double)> scored = <(PantryItemView, double)>[
    for (final PantryItemView item in items)
      if (!item.isStaple && item.quantity > 0)
        (item, scorePantryItem(item, now: effectiveNow)),
  ]..sort((a, b) => b.$2.compareTo(a.$2));

  return <CompressedPantryItem>[
    for (final (PantryItemView item, double score) in scored.take(topN))
      CompressedPantryItem(
        id: item.ingredientId,
        name: item.canonicalName,
        quantity: item.quantity,
        unit: item.unit,
        foodGroup: item.foodGroup,
        urgencyScore: score,
      ),
  ];
}
