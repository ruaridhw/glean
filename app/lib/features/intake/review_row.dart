import 'package:flutter/widgets.dart';
import 'package:glean/router/intake_params.dart';

import '../pantry/pantry_presentation.dart';

/// Per-row editable state for [ReviewScreen]. Quantity/name/unit are
/// free-typed text (no `String(quantity)` round-trip); [category] is the one
/// field with no text controller, since it's chosen from a fixed taxonomy,
/// not typed.
class ReviewRow {
  ReviewRow(ReviewItemDraft draft)
    : reviewId = draft.reviewId,
      nameController = TextEditingController(text: draft.name),
      quantityController = TextEditingController(
        text: formatQuantitySeed(draft.quantity),
      ),
      unitController = TextEditingController(text: draft.unit),
      confidence = draft.confidence,
      unitPrice = draft.unitPrice,
      category = draft.category;

  final String reviewId;
  final TextEditingController nameController;
  final TextEditingController quantityController;
  final TextEditingController unitController;
  final double confidence;
  final double? unitPrice;
  String? category;

  /// Whether this row will be persisted at all — clearing the name is an
  /// alternate way to drop a row, without requiring the explicit remove
  /// button (mirrors the RN review screens' name-based `acceptedItems`
  /// filter).
  bool get isActive => nameController.text.trim().isNotEmpty;

  /// Null for anything unparseable, non-finite, zero or negative — no
  /// fallback value (AC-PAN-08/09; see `parsePositiveQuantity`'s doc for why
  /// there is deliberately no fallback rule at all).
  double? get parsedQuantity => parsePositiveQuantity(quantityController.text);

  void dispose() {
    nameController.dispose();
    quantityController.dispose();
    unitController.dispose();
  }
}
