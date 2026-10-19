import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/models/receipts.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'fixture.dart';

void main() {
  test(
    'serialized backend proposals persist against the actual seeded ingredient groups',
    () async {
      final response = ScanResponse.fromJson(
        jsonDecode(
              File(
                '../backend/tests/fixtures/receipt_taxonomy.json',
              ).readAsStringSync(),
            )
            as Map<String, dynamic>,
      );
      final db = createTestDatabase();
      addTearDown(db.close);
      final ingredients = IngredientsRepository(db);
      final shopping = ShoppingRepository(db, ingredients);
      await shopping.addAiItems(
        userId: 'contract',
        items: [
          for (final item in response.items)
            AiShoppingItem(
              name: item.name,
              quantity: item.quantity,
              unit: item.unit,
              groupId: item.groupId,
            ),
        ],
      );
      final pantry = PantryRepository(db, ingredients);
      for (final item in response.items.where((item) => item.groupId != null)) {
        await pantry.addItem(
          userId: 'contract',
          name: item.name,
          quantity: item.quantity,
          unit: item.unit,
          groupId: item.groupId!,
        );
      }
      final saved = await pantry.getAll('contract');
      for (final item in response.items.where((item) => item.groupId != null)) {
        final row = saved.singleWhere(
          (row) => row.canonicalName == item.name.toLowerCase(),
        );
        expect(row.groupId, item.ingredientGroup);
        expect(row.foodGroup, item.foodGroup);
      }
      final seeded = {
        for (final row in await db.select(db.ingredientGroups).get())
          row.id: row.foodGroup,
      };
      expect(
        {
          for (final item in response.items.where(
            (item) => item.ingredientGroup != null,
          ))
            item.ingredientGroup!: item.foodGroup,
        },
        {
          for (final entry in seeded.entries)
            if (response.items.any((i) => i.ingredientGroup == entry.key))
              entry.key: entry.value,
        },
      );
      expect(
        (await shopping.watchAll('contract').first).length,
        response.items.length,
      );
    },
  );
}
