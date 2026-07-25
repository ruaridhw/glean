/// Typed nav-param objects for the intake flow (scan → progress → review),
/// passed as `GoRoute` `extra`.
///
/// This is the direct fix for the RN bug this port must not reproduce: the
/// old app serialised these to JSON strings in URL-style params and did an
/// unguarded `JSON.parse` on the way back out, which could white-screen a
/// route with no back button (§11). Passing real Dart objects makes that
/// failure mode structurally impossible — there is no decode step to fail.
library;

import 'package:flutter/foundation.dart';

/// Which flow the shared intake review screen (AC-PAN-05) is completing.
/// Everything else about *what* gets written where is feature logic (Wave 3
/// Pantry/Shop); the router only needs to know which route to land on
/// afterwards and which destination screen to render.
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
  });

  /// Stable identity assigned once when the draft list is built. List key
  /// only — never persisted (mirrors `ReviewItem.review_id` in the RN app).
  final String reviewId;
  final String name;
  final double quantity;
  final String unit;
  final double confidence;

  /// Pantry-only; always null for shop drafts.
  final double? unitPrice;

  ReviewItemDraft copyWith({
    String? name,
    double? quantity,
    String? unit,
    double? confidence,
    double? unitPrice,
  }) {
    return ReviewItemDraft(
      reviewId: reviewId,
      name: name ?? this.name,
      quantity: quantity ?? this.quantity,
      unit: unit ?? this.unit,
      confidence: confidence ?? this.confidence,
      unitPrice: unitPrice ?? this.unitPrice,
    );
  }

  @override
  bool operator ==(Object other) =>
      other is ReviewItemDraft &&
      other.reviewId == reviewId &&
      other.name == name &&
      other.quantity == quantity &&
      other.unit == unit &&
      other.confidence == confidence &&
      other.unitPrice == unitPrice;

  @override
  int get hashCode =>
      Object.hash(reviewId, name, quantity, unit, confidence, unitPrice);
}

/// Typed `extra` for [AppRoutes.intakeReview].
@immutable
class ReviewArgs {
  const ReviewArgs({
    required this.destination,
    required this.items,
    this.clarifyingQuestions = const <String>[],
    this.returnToShop = false,
  });

  final ReviewDestination destination;
  final List<ReviewItemDraft> items;

  /// Shop-describe only; empty for every other entry point.
  final List<String> clarifyingQuestions;

  /// True when this pantry review was reached via "scan receipt" from the
  /// Shop tab's checkout bar, so confirming should also complete the
  /// shopping checkout (see `completeCheckout` in the RN app). Always false
  /// for `destination == shop`.
  final bool returnToShop;

  @override
  bool operator ==(Object other) =>
      other is ReviewArgs &&
      other.destination == destination &&
      listEquals(other.items, items) &&
      listEquals(other.clarifyingQuestions, clarifyingQuestions) &&
      other.returnToShop == returnToShop;

  @override
  int get hashCode => Object.hash(
    destination,
    Object.hashAll(items),
    Object.hashAll(clarifyingQuestions),
    returnToShop,
  );
}

/// Typed `extra` for [AppRoutes.intakeScan].
@immutable
class ScanArgs {
  const ScanArgs({this.returnToShop = false});

  /// Mirrors `ReviewArgs.returnToShop` — carried through scan → progress →
  /// review so the whole chain agrees on where it's going.
  final bool returnToShop;

  @override
  bool operator ==(Object other) =>
      other is ScanArgs && other.returnToShop == returnToShop;

  @override
  int get hashCode => returnToShop.hashCode;
}

/// Typed `extra` for [AppRoutes.intakeScanProgress].
@immutable
class ScanProgressArgs {
  const ScanProgressArgs({required this.photoBytes, this.returnToShop = false});

  /// The captured JPEG, in memory. The RN app base64-encoded this into a nav
  /// param string; passing raw bytes avoids that encode/decode round trip
  /// entirely rather than just guarding it.
  final Uint8List photoBytes;
  final bool returnToShop;

  @override
  bool operator ==(Object other) =>
      other is ScanProgressArgs &&
      listEquals(other.photoBytes, photoBytes) &&
      other.returnToShop == returnToShop;

  @override
  int get hashCode => Object.hash(Object.hashAll(photoBytes), returnToShop);
}
