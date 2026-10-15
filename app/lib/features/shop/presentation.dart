/// Pure presentation helpers for the Shop tab. [cartCountLabel] and [inCartSectionTitle] are the only two
/// phrasings used for the checked-item count, so every call site says the same thing.
library;

import '../../data/models/shopping_list_item_view.dart';

/// Bold row label: "name · 200 g", or just the name when there's no quantity recorded.
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

/// Every render of a plan-derived row carries a visible tag, so its origin is never a mystery after the
/// insertion itself (done by the Plan feature via `ShoppingRepository.addGapsForRecipe`).
bool isPlanDerived(ShoppingListItemView item) =>
    item.source == ShoppingSource.mealPlan;

/// The one phrase for "N items are checked off, ready to buy", used by the count chip and the checkout bar.
String cartCountLabel(int checkedCount) =>
    '$checkedCount ${checkedCount == 1 ? 'item' : 'items'} in cart';

String toBuyCountLabel(int uncheckedCount) =>
    '$uncheckedCount ${uncheckedCount == 1 ? 'item' : 'items'} to buy';

/// Section header over the checked rows: the same "in cart" vocabulary as [cartCountLabel], without a count
/// (there's already one in the chip row).
const String inCartSectionTitle = 'In cart';
const String toBuySectionTitle = 'To buy';
