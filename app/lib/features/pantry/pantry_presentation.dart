/// Pure presentation helpers for the Pantry screen: grouping, expiry badges and the "expiring soon" predicate
/// used by the header chip and the Plan nudge. Free of Flutter/Riverpod so it stays unit-testable.
library;

import 'package:flutter/material.dart';
import 'package:glean/data/models/pantry_item_view.dart';

/// Display metadata for a pantry section, keyed by food group. Several food groups fold into one display
/// section (`vegetables` and `fruit` under "Veg & Fruit"; `carbohydrates`/`fats`/`condiments` under "Cupboard"),
/// since the pantry groups coarser than the 23-category taxonomy.
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

/// Resolves display metadata for a raw `foodGroup` string, falling back to "Other" so an unknown food group never
/// vanishes from the UI.
PantryCategoryMeta pantryCategoryMeta(String foodGroup) =>
    _byFoodGroup[foodGroup] ?? _other;

/// One display section of the grouped pantry list.
class PantrySection {
  const PantrySection({required this.meta, required this.items});

  final PantryCategoryMeta meta;
  final List<PantryItemView> items;
}

/// Groups [items] by display section (see [pantryCategoryMeta]), preserving each section's first-seen order from
/// the (expiry-sorted) input.
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

/// Renders a quantity without a trailing ".0" for whole numbers.
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

/// Tone for an expiry badge.
enum ExpiryTone { expired, soon, later }

@immutable
class ExpiryBadge {
  const ExpiryBadge({required this.label, required this.tone});

  final String label;
  final ExpiryTone tone;
}

/// Builds the expiry badge for [expiryDate] relative to [now], or null when there is nothing to show (a null
/// expiry, e.g. a category-less item, shows no badge rather than a fabricated one).
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

/// Whether [item] counts toward the "N expiring" chip/banner: expired or within a couple of days. Shared by the
/// pantry header and the Plan nudge so both stay in lockstep.
bool isExpiringSoon(PantryItemView item, {DateTime? now}) {
  final ExpiryBadge? badge = expiryBadgeFor(item.expiryDate, now: now);
  return badge?.tone == ExpiryTone.expired || badge?.tone == ExpiryTone.soon;
}

/// Parses a user-typed quantity, returning null for anything that isn't a finite positive number.
///
/// This is the single fallback rule shared by manual entry, the quantity edit sheet and the review screen. There
/// is no fallback: an unparseable, zero, negative or NaN value is invalid (null), and every call site must block
/// the action rather than substitute a magic number.
double? parsePositiveQuantity(String text) {
  final String trimmed = text.trim();
  if (trimmed.isEmpty) return null;
  final double? value = double.tryParse(trimmed);
  if (value == null || !value.isFinite || value <= 0) return null;
  return value;
}

/// Formats a quantity for an editable field's seed text, dropping a trailing ".0" for whole numbers. Typing
/// further is unrestricted free text: nothing re-derives the text from the numeric value on every keystroke.
String formatQuantitySeed(double quantity) {
  if (quantity == quantity.roundToDouble()) return quantity.toStringAsFixed(0);
  String text = quantity.toStringAsFixed(3);
  text = text.replaceFirst(RegExp(r'0+$'), '');
  text = text.replaceFirst(RegExp(r'\.$'), '');
  return text;
}

/// A human-readable label for a taxonomy category key (e.g. `leafy_greens` -> `Leafy Greens`), shared by manual
/// entry's and the review screen's category pickers.
String categoryLabel(String key) => key
    .split('_')
    .map((String w) => '${w[0].toUpperCase()}${w.substring(1)}')
    .join(' ');
