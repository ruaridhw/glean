import 'package:flutter/widgets.dart';
import 'package:glean/router/intake_params.dart';

import '../pantry/pantry_presentation.dart';

/// Per-row editable state for [ReviewScreen]. Quantity/name/unit are
/// free-typed text (no `String(quantity)` round-trip); [category] is the one
/// field with no text controller, since it's chosen from a fixed taxonomy,
/// not typed.
class ReviewRow {
  ReviewRow(ReviewItemDraft draft)
    : _proposal = draft,
      originalName = draft.name.trim().toLowerCase(),
      reviewId = draft.reviewId,
      nameController = TextEditingController(text: draft.name),
      quantityController = TextEditingController(
        text: formatQuantitySeed(draft.quantity),
      ),
      unitController = TextEditingController(text: draft.unit),
      confidence = draft.confidence,
      unitPrice = draft.unitPrice,
      category = draft.category,
      sourceRowIds = draft.sourceRowIds;

  final String originalName;
  bool selected = true;
  final String reviewId;

  /// The Shopping rows this row came from, when it was pre-filled from the list.
  final List<int> sourceRowIds;
  final TextEditingController nameController;
  final TextEditingController quantityController;
  final TextEditingController unitController;
  ReviewItemDraft _proposal;
  double confidence;
  double? unitPrice;
  String? category;

  /// Whether this row will be persisted at all: clearing the name is an alternate way to drop a row.
  bool get isActive => selected && nameController.text.trim().isNotEmpty;

  /// Null for anything unparseable, non-finite, zero or negative; there is deliberately no fallback (see
  /// `parsePositiveQuantity`).
  double? get parsedQuantity => parsePositiveQuantity(quantityController.text);

  /// Adopt refined values only in fields the user has not edited.
  void refine(ReviewItemDraft proposal) {
    if (nameController.text == _proposal.name) {
      nameController.text = proposal.name;
    }
    if (quantityController.text == formatQuantitySeed(_proposal.quantity)) {
      quantityController.text = formatQuantitySeed(proposal.quantity);
    }
    if (unitController.text == _proposal.unit) {
      unitController.text = proposal.unit;
    }
    if (category == _proposal.category) category = proposal.category;
    confidence = proposal.confidence;
    unitPrice = proposal.unitPrice;
    _proposal = proposal;
  }

  void dispose() {
    nameController.dispose();
    quantityController.dispose();
    unitController.dispose();
  }
}
