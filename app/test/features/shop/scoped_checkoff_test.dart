// AC-SHOP-04: `checkOffResolvedIngredients` — called when a scanned receipt
// resolves an ingredient, to tick off the matching shopping row even if the
// user hadn't ticked it themselves — must never cross a user boundary and
// must never re-affect a row that's already checked. This is a pure
// data-contract check (no screen involved), so it uses the shared in-memory
// fixture directly rather than pumping a widget through `AppTestHarness`.
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/shopping_list_item_view.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';

import '../../data/fixture.dart';

void main() {
  test('checking off for one user never touches another user\'s matching row '
      '(AC-SHOP-04)', () async {
    final db = createTestDatabase();
    addTearDown(db.close);
    final ingredients = IngredientsRepository(db);
    final shopping = ShoppingRepository(db, ingredients);

    final int userAItemId = await shopping.addManualItem(
      userId: 'user-a',
      name: 'Milk',
    );
    await shopping.addManualItem(userId: 'user-b', name: 'Milk');
    final ingredient = await ingredients.resolveOrCreate(canonicalName: 'Milk');

    await shopping.checkOffResolvedIngredients(
      userId: 'user-a',
      ingredientIds: <int>[ingredient.id],
    );

    final List<ShoppingListItemView> userARows = await shopping
        .watchAll('user-a')
        .first;
    final List<ShoppingListItemView> userBRows = await shopping
        .watchAll('user-b')
        .first;
    expect(
      userARows.firstWhere((row) => row.id == userAItemId).isChecked,
      isTrue,
    );
    expect(userBRows.single.isChecked, isFalse);
  });

  test('checking off never re-affects a row that is already checked '
      '(AC-SHOP-04)', () async {
    final db = createTestDatabase();
    addTearDown(db.close);
    final ingredients = IngredientsRepository(db);
    final shopping = ShoppingRepository(db, ingredients);

    final int id = await shopping.addManualItem(userId: 'user-a', name: 'Milk');
    await shopping.toggleItem(id: id, userId: 'user-a', checked: true);
    final ingredient = await ingredients.resolveOrCreate(canonicalName: 'Milk');

    // Idempotent: calling this again for an already-checked row must not
    // error and must not "double-check" it into some other state.
    await shopping.checkOffResolvedIngredients(
      userId: 'user-a',
      ingredientIds: <int>[ingredient.id],
    );

    final List<ShoppingListItemView> rows = await shopping
        .watchAll('user-a')
        .first;
    expect(rows.single.isChecked, isTrue);
  });
}
