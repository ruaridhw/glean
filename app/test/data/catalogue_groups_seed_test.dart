import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

import 'fixture.dart';

void main() {
  test('a fresh install has the backend\'s 29 ingredient groups and their '
      'defaults before any sync', () async {
    final db = createTestDatabase();
    addTearDown(db.close);
    final expected =
        jsonDecode(
              File(
                'test/data/fixtures/catalogue_groups.json',
              ).readAsStringSync(),
            )
            as List<dynamic>;

    final stored = await db.select(db.ingredientGroups).get();

    expect(stored, hasLength(29));
    final byId = {for (final g in stored) g.id: g};
    for (final dynamic raw in expected) {
      final Map<String, dynamic> group = raw as Map<String, dynamic>;
      final row = byId[group['id']]!;
      expect(row.name, group['name']);
      expect(row.kind, group['kind']);
      expect(row.foodGroup, group['food_group']);
      expect(row.trackingMode, group['tracking_mode']);
      expect(row.stockUnit, group['stock_unit']);
      expect(jsonDecode(row.allowedForms), group['allowed_forms']);
      expect(
        jsonDecode(row.unopenedShelfLifeDays),
        group['unopened_shelf_life_days'],
      );
      expect(
        jsonDecode(row.onceOpenedShelfLifeDays),
        group['once_opened_shelf_life_days'],
      );
    }
  });

  test('a fresh install starts with no catalogue items, aliases or sync '
      'state', () async {
    final db = createTestDatabase();
    addTearDown(db.close);

    expect(await db.select(db.catalogueItems).get(), isEmpty);
    expect(await db.select(db.catalogueAliases).get(), isEmpty);
    expect(await db.select(db.catalogueSyncState).get(), isEmpty);
  });
}
