import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';

import 'fixture.dart';

void main() {
  test(
    'deleted stock restores null expiry, identity, price and prior usage',
    () async {
      final db = createTestDatabase();
      addTearDown(db.close);
      final pantry = PantryRepository(db, IngredientsRepository(db));
      await pantry.addItem(
        userId: 'a',
        name: 'butter',
        quantity: 250,
        unit: 'g',
        category: 'dairy',
        unitPrice: 2.5,
      );
      await db.customStatement(
        "UPDATE pantry_items SET expiry_date=NULL, last_used_at='2026-01-02T00:00:00.000'",
      );
      final before = (await pantry.getAll('a')).single;
      await pantry.deleteItem(id: before.id, userId: 'a');
      await pantry.restoreDeletedItem(userId: 'a', item: before);
      final restored = (await pantry.getAll('a')).single;
      expect(restored.id, before.id);
      expect(restored.expiryDate, isNull);
      expect(restored.lastUsedAt, before.lastUsedAt);
      expect(restored.unitPrice, 2.5);
      expect(restored.quantity, 250);
    },
  );

  test(
    'Undo merges quantity into concurrent stock without overwriting its metadata',
    () async {
      final db = createTestDatabase();
      addTearDown(db.close);
      final pantry = PantryRepository(db, IngredientsRepository(db));
      await pantry.addItem(
        userId: 'a',
        name: 'butter',
        quantity: 250,
        unit: 'g',
        category: 'dairy',
        now: DateTime(2026, 1, 1),
      );
      final deleted = (await pantry.getAll('a')).single;
      await pantry.deleteItem(id: deleted.id, userId: 'a');
      await pantry.addItem(
        userId: 'a',
        name: 'butter',
        quantity: 100,
        unit: 'g',
        category: 'dairy',
        unitPrice: 3,
        now: DateTime(2026, 2, 1),
      );
      final fresh = (await pantry.getAll('a')).single;
      await pantry.restoreDeletedItem(userId: 'a', item: deleted);
      final merged = (await pantry.getAll('a')).single;
      expect(merged.quantity, 350);
      expect(merged.id, fresh.id);
      expect(merged.expiryDate, fresh.expiryDate);
      expect(merged.unitPrice, fresh.unitPrice);
      expect(merged.lastUsedAt, fresh.lastUsedAt);
    },
  );

  test('cannot restore another owner snapshot', () async {
    final db = createTestDatabase();
    addTearDown(db.close);
    final pantry = PantryRepository(db, IngredientsRepository(db));
    await pantry.addItem(
      userId: 'a',
      name: 'butter',
      quantity: 250,
      unit: 'g',
      category: 'dairy',
    );
    final item = (await pantry.getAll('a')).single;
    expect(
      () => pantry.restoreDeletedItem(userId: 'b', item: item),
      throwsStateError,
    );
    expect(await pantry.getAll('b'), isEmpty);
  });
}
