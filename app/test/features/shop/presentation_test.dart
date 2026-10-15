// Pure-function coverage for `lib/features/shop/presentation.dart` — no
// widget/database needed.
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/shopping_list_item_view.dart';
import 'package:glean/features/shop/presentation.dart';

ShoppingListItemView _item({
  int id = 1,
  double? quantity,
  String? unit,
  String source = 'manual',
  bool isChecked = false,
}) {
  return ShoppingListItemView(
    id: id,
    userId: 'test-user',
    ingredientId: 1,
    name: 'Milk',
    quantity: quantity,
    unit: unit,
    source: source,
    isChecked: isChecked,
    sourceMealPlanEntryId: null,
  );
}

void main() {
  group('formatShoppingItemLabel', () {
    test('renders "name · quantity unit" when both are present', () {
      expect(
        formatShoppingItemLabel(_item(quantity: 2, unit: 'l')),
        'Milk · 2 l',
      );
    });

    test('drops the trailing .0 for a whole-number quantity', () {
      expect(formatShoppingItemLabel(_item(quantity: 4)), 'Milk · 4');
    });

    test('keeps a decimal quantity as typed', () {
      expect(
        formatShoppingItemLabel(_item(quantity: 1.5, unit: 'kg')),
        'Milk · 1.5 kg',
      );
    });

    test('is just the name when there is no quantity', () {
      expect(formatShoppingItemLabel(_item()), 'Milk');
    });
  });

  group('isPlanDerived', () {
    test('true only for a meal_plan-sourced row', () {
      expect(isPlanDerived(_item(source: 'meal_plan')), isTrue);
      expect(isPlanDerived(_item(source: 'manual')), isFalse);
      expect(isPlanDerived(_item(source: 'ai')), isFalse);
    });
  });

  group('AC-SHOP-07 — one phrase for the cart count', () {
    test('cartCountLabel pluralizes correctly', () {
      expect(cartCountLabel(0), '0 items in cart');
      expect(cartCountLabel(1), '1 item in cart');
      expect(cartCountLabel(4), '4 items in cart');
    });

    test('toBuyCountLabel pluralizes correctly', () {
      expect(toBuyCountLabel(1), '1 item to buy');
      expect(toBuyCountLabel(3), '3 items to buy');
    });
  });
}
