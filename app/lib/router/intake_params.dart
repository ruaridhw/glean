/// Typed `extra` objects for the intake flow (scan, progress, review).
library;

import 'package:flutter/foundation.dart';

/// Which flow the shared intake review screen is completing.
enum ReviewDestination { pantry, shop }

/// One AI-extracted candidate item awaiting user review, in flight between
/// the scan/describe screens and the review screen.
@immutable
class ReviewItemDraft {
  const ReviewItemDraft({
    required this.reviewId,
    required this.name,
    required this.quantity,
    required this.unit,
    required this.confidence,
    this.unitPrice,
    this.category,
    this.sourceRowIds = const <int>[],
  });

  /// Stable list key assigned once when the draft list is built; never persisted.
  final String reviewId;
  final String name;
  final double quantity;
  final String unit;
  final double confidence;

  /// Pantry-only; always null for shop drafts.
  final double? unitPrice;

  /// Backend-classified taxonomy category; null when the backend could not classify it.
  final String? category;

  /// The Shopping rows this draft stands for ("Done shopping" only); confirming clears exactly these.
  final List<int> sourceRowIds;

  ReviewItemDraft copyWith({
    String? name,
    double? quantity,
    String? unit,
    double? confidence,
    double? unitPrice,
    String? category,
  }) {
    return ReviewItemDraft(
      reviewId: reviewId,
      name: name ?? this.name,
      quantity: quantity ?? this.quantity,
      unit: unit ?? this.unit,
      confidence: confidence ?? this.confidence,
      unitPrice: unitPrice ?? this.unitPrice,
      category: category ?? this.category,
      sourceRowIds: sourceRowIds,
    );
  }
}

/// `extra` for [AppRoutes.intakeReview]: the items to review and which flow they complete.
@immutable
class ReviewArgs {
  const ReviewArgs({
    required this.destination,
    required this.items,
    this.clarifyingQuestions = const <String>[],
    this.originalDescription,
    this.returnToShop = false,
    this.fromCheckedItems = false,
  });

  final ReviewDestination destination;
  final List<ReviewItemDraft> items;

  /// Shop-describe only; empty for every other entry point.
  final List<String> clarifyingQuestions;
  final String? originalDescription;

  /// True when this pantry review came from the Shop checkout bar's "scan receipt".
  final bool returnToShop;

  /// True when the items are the Shop tab's checked rows ("Done shopping"), not a parse response. Confirming
  /// adds them to the pantry and clears them from the list in one step, with one Undo for both.
  final bool fromCheckedItems;
}

/// `extra` for [AppRoutes.intakeScan]: whether the chain returns to the Shop tab.
@immutable
class ScanArgs {
  const ScanArgs({this.returnToShop = false});

  final bool returnToShop;
}

/// `extra` for [AppRoutes.intakeScanProgress]: the captured photo to parse.
@immutable
class ScanProgressArgs {
  const ScanProgressArgs({required this.photoBytes, this.returnToShop = false});

  /// The captured JPEG, in memory.
  final Uint8List photoBytes;
  final bool returnToShop;
}
