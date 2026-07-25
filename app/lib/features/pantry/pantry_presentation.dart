/// Pure presentation helpers for the Pantry screen, ported from
/// `mobile/src/pantry/presentation.ts` — grouping, expiry badges and the
/// "expiring soon" predicate the header chip and (eventually) the Plan nudge
/// both rely on. Kept free of Flutter/Riverpod so it stays unit-testable in
/// isolation from widgets (AC-TEST-05 style: this is the highest-value
/// logic-port candidate in this feature).
library;

import 'package:flutter/material.dart';
import 'package:glean/data/models/pantry_item_view.dart';

/// Display metadata for a pantry section, keyed by food group. Several food
/// groups fold into the same display section — RN groups `vegetables` and
/// `fruit` under one "Veg & Fruit" header, and `carbohydrates`/`fats`/
/// `condiments` under one "Cupboard" header — because the pantry UI groups
/// coarser than the 23-category taxonomy.
@immutable
class PantryCategoryMeta {
  const PantryCategoryMeta({
    required this.key,
    required this.label,
    required this.shortLabel,
    required this.icon,
  });

  /// The display-section key (used for filter chips and section identity),
  /// distinct from the underlying `foodGroup` string — e.g. both
  /// `vegetables` and `fruit` map to the `veg_fruit` section key.
  final String key;
  final String label;

  /// Short form for filter chips (e.g. "Veg" for "Veg & Fruit").
  final String shortLabel;
  final IconData icon;
}

const Map<String, PantryCategoryMeta> _byFoodGroup =
    <String, PantryCategoryMeta>{
      'vegetables': PantryCategoryMeta(
        key: 'veg_fruit',
        label: 'Veg & Fruit',
        shortLabel: 'Veg',
        icon: Icons.eco_rounded,
      ),
      'fruit': PantryCategoryMeta(
        key: 'veg_fruit',
        label: 'Veg & Fruit',
        shortLabel: 'Veg',
        icon: Icons.eco_rounded,
      ),
      'protein': PantryCategoryMeta(
        key: 'protein',
        label: 'Meat & Fish',
        shortLabel: 'Meat',
        icon: Icons.set_meal_rounded,
      ),
      'dairy': PantryCategoryMeta(
        key: 'dairy',
        label: 'Dairy',
        shortLabel: 'Dairy',
        icon: Icons.water_drop_rounded,
      ),
      'carbohydrates': PantryCategoryMeta(
        key: 'cupboard',
        label: 'Cupboard',
        shortLabel: 'Cupboard',
        icon: Icons.inventory_2_rounded,
      ),
      'fats': PantryCategoryMeta(
        key: 'cupboard',
        label: 'Cupboard',
        shortLabel: 'Cupboard',
        icon: Icons.inventory_2_rounded,
      ),
      'condiments': PantryCategoryMeta(
        key: 'cupboard',
        label: 'Cupboard',
        shortLabel: 'Cupboard',
        icon: Icons.inventory_2_rounded,
      ),
      'frozen': PantryCategoryMeta(
        key: 'frozen',
        label: 'Frozen',
        shortLabel: 'Frozen',
        icon: Icons.ac_unit_rounded,
      ),
    };

const PantryCategoryMeta _other = PantryCategoryMeta(
  key: 'other',
  label: 'Other',
  shortLabel: 'Other',
  icon: Icons.category_rounded,
);

/// Resolves display metadata for a raw `foodGroup` string, falling back to
/// "Other" for anything unrecognised — mirrors `getPantryCategoryMeta` in the
/// RN app, which never lets an unknown food group vanish from the UI.
PantryCategoryMeta pantryCategoryMeta(String foodGroup) =>
    _byFoodGroup[foodGroup] ?? _other;

/// One display section of the grouped pantry list.
class PantrySection {
  const PantrySection({required this.meta, required this.items});

  final PantryCategoryMeta meta;
  final List<PantryItemView> items;
}

/// Groups [items] by display section (see [pantryCategoryMeta]), preserving
/// each section's first-seen order — matches RN's `groupPantryItems`, which
/// builds sections in the order their first item appears in the
/// (expiry-sorted) input list.
List<PantrySection> groupPantryItems(List<PantryItemView> items) {
  final Map<String, List<PantryItemView>> byKey =
      <String, List<PantryItemView>>{};
  final Map<String, PantryCategoryMeta> metaByKey =
      <String, PantryCategoryMeta>{};

  for (final PantryItemView item in items) {
    final PantryCategoryMeta meta = pantryCategoryMeta(item.foodGroup);
    byKey.putIfAbsent(meta.key, () => <PantryItemView>[]).add(item);
    metaByKey[meta.key] = meta;
  }

  return <PantrySection>[
    for (final MapEntry<String, List<PantryItemView>> entry in byKey.entries)
      PantrySection(meta: metaByKey[entry.key]!, items: entry.value),
  ];
}

/// Renders a quantity without a trailing ".0" for whole numbers, matching RN's
/// `formatPantryQuantity`.
String formatPantryQuantity(double quantity, String unit) {
  final String qtyText = quantity == quantity.roundToDouble()
      ? quantity.toStringAsFixed(0)
      : _trimTrailingZeros(quantity);
  return '$qtyText $unit';
}

String _trimTrailingZeros(double value) {
  String text = value.toStringAsFixed(2);
  if (text.contains('.')) {
    text = text.replaceFirst(RegExp(r'0+$'), '');
    text = text.replaceFirst(RegExp(r'\.$'), '');
  }
  return text;
}

/// Tone for an expiry badge, matching RN's `ExpiryBadgeModel.tone`.
enum ExpiryTone { expired, soon, later }

@immutable
class ExpiryBadge {
  const ExpiryBadge({required this.label, required this.tone});

  final String label;
  final ExpiryTone tone;
}

/// Builds the expiry badge for [expiryDate] relative to [now], or null when
/// there is nothing to show (AC-PAN-02: driven from real stored data, so a
/// null expiry — a category-less item degrading gracefully, FINDINGS.md
/// F-07/F-08 — simply shows no badge rather than a fabricated one). Ported
/// from RN's `getExpiryBadge`.
ExpiryBadge? expiryBadgeFor(DateTime? expiryDate, {DateTime? now}) {
  if (expiryDate == null) return null;

  final DateTime today = _dateOnly(now ?? DateTime.now());
  final DateTime expiry = _dateOnly(expiryDate);
  final int days = expiry.difference(today).inDays;

  if (days < 0) {
    return const ExpiryBadge(label: 'Expired', tone: ExpiryTone.expired);
  }
  if (days == 0) {
    return const ExpiryBadge(label: 'Today', tone: ExpiryTone.expired);
  }
  if (days <= 2) {
    return ExpiryBadge(label: '${days}d left', tone: ExpiryTone.soon);
  }
  return ExpiryBadge(label: '${days}d left', tone: ExpiryTone.later);
}

DateTime _dateOnly(DateTime date) => DateTime(date.year, date.month, date.day);

/// Whether [item] counts toward the "N expiring" chip/banner — expired or
/// within a couple of days (`ExpiryTone.expired`/`.soon`). Shared by the
/// pantry header and (via the same stored `expiryDate`) the Plan nudge, so
/// both stay in lockstep — mirrors RN's `isExpiringSoon`.
bool isExpiringSoon(PantryItemView item, {DateTime? now}) {
  final ExpiryBadge? badge = expiryBadgeFor(item.expiryDate, now: now);
  return badge?.tone == ExpiryTone.expired || badge?.tone == ExpiryTone.soon;
}

/// Parses a user-typed quantity, returning null for anything that isn't a
/// finite positive number.
///
/// This is the single fallback rule shared by manual entry, the quantity
/// edit sheet and the intake review screen — the direct fix for §11's
/// "inconsistent numeric fallbacks between the twin review screens" (one
/// fell back to `1`, the other to `0`). There is no fallback at all: an
/// unparseable, zero, negative or NaN value is simply invalid (null), and
/// every call site must block the destructive action rather than silently
/// substituting a magic number (AC-PAN-08/09).
double? parsePositiveQuantity(String text) {
  final String trimmed = text.trim();
  if (trimmed.isEmpty) return null;
  final double? value = double.tryParse(trimmed);
  if (value == null || !value.isFinite || value <= 0) return null;
  return value;
}

/// Formats a quantity for an editable text field's seed text, dropping a
/// trailing ".0" for whole numbers — the starting text a
/// `TextEditingController` is built with (in the review screen's rows and
/// the quantity edit sheet alike). Typing further is unrestricted free text
/// (AC-PAN-08): unlike RN's `String(quantity)` seed, nothing here re-derives
/// the text from the numeric value on every keystroke, so there is no
/// round-trip to fight.
String formatQuantitySeed(double quantity) {
  if (quantity == quantity.roundToDouble()) return quantity.toStringAsFixed(0);
  String text = quantity.toStringAsFixed(3);
  text = text.replaceFirst(RegExp(r'0+$'), '');
  text = text.replaceFirst(RegExp(r'\.$'), '');
  return text;
}

/// A human-readable label for a taxonomy category key (e.g. `leafy_greens`
/// -> `Leafy Greens`). Shared by manual entry's category picker and the
/// review screen's per-row category picker (shown when a parsed item has no
/// category, FINDINGS.md F-07/F-08) — one label format everywhere a raw
/// taxonomy key reaches the UI.
String categoryLabel(String key) => key
    .split('_')
    .map((String w) => '${w[0].toUpperCase()}${w.substring(1)}')
    .join(' ');
