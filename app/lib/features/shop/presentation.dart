/// Pure presentation helpers for the Shop tab, ported from the Expo app's
/// `src/shop/presentation.ts` (see git history).
///
/// AC-SHOP-07 folds in here too: RN said "N checked" (a chip), "N items in
/// cart" (the checkout bar) and "In your cart" (a section header) for the
/// exact same state. [cartCountLabel] and [inCartSectionTitle] are the only
/// two phrasings used anywhere in this feature for that count, so every call
/// site says the same thing.
library;

import '../../data/models/shopping_list_item_view.dart';

/// Bold row label — "name · 200 g", or just the name when there's no
/// quantity recorded (a manual entry added with no amount).
String formatShoppingItemLabel(ShoppingListItemView item) {
  if (item.quantity == null) return item.name;
  final String unit = item.unit ?? '';
  final String quantity = <String>[
    _formatQuantity(item.quantity!),
    if (unit.isNotEmpty) unit,
  ].join(' ');
  return quantity.isEmpty ? item.name : '${item.name} · $quantity';
}

String _formatQuantity(double quantity) {
  return quantity == quantity.roundToDouble()
      ? quantity.toStringAsFixed(0)
      : quantity.toString();
}

/// AC-SHOP-05: a plan-derived row was inserted *silently* in RN. This can't
/// fully satisfy the criterion on its own — the insertion itself happens in
/// the Plan feature (`ShoppingRepository.addGapsForRecipe`, called from
/// outside this module), which is where a one-off confirmation snackbar
/// belongs. What this module owns is making sure the row's origin is never a
/// mystery *after* that moment: every render of a plan-derived row carries a
/// visible tag, not just its first appearance.
bool isPlanDerived(ShoppingListItemView item) => item.source == 'meal_plan';

/// The one phrase for "N items are checked off, ready to buy" — used by both
/// the count chip and the checkout bar.
String cartCountLabel(int checkedCount) =>
    '$checkedCount ${checkedCount == 1 ? 'item' : 'items'} in cart';

String toBuyCountLabel(int uncheckedCount) =>
    '$uncheckedCount ${uncheckedCount == 1 ? 'item' : 'items'} to buy';

/// Section header over the checked rows — the same "in cart" vocabulary as
/// [cartCountLabel], just without a count (there's already one right above
/// the list in the chip row).
const String inCartSectionTitle = 'In cart';
const String toBuySectionTitle = 'To buy';
