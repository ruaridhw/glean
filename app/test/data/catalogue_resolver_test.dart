// `effectiveIngredient` is the one place a catalogue item's tracking mode, stock unit, shelf lives and store section
// are decided: the household's override, else the item, else its ingredient group's default, field by field.
import 'package:drift/drift.dart' show Value;
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/api.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/repositories/catalogue_repository.dart';

import 'fixture.dart';

Map<String, Object?> _item(
  String id, {
  String group = 'spices',
  String form = 'not_applicable',
  String? section,
  Map<String, Object?> overrides = const <String, Object?>{},
  List<String> formerIds = const <String>[],
}) => <String, Object?>{
  'id': id,
  'name': id,
  'group': group,
  'form': form,
  'overrides': <String, Object?>{
    'tracking_mode': null,
    'stock_unit': null,
    'unopened_shelf_life_days': null,
    'once_opened_shelf_life_days': null,
    ...overrides,
  },
  'density_g_per_ml': null,
  'source': 'seed',
  'section': ?section,
  'former_ids': formerIds,
};

void main() {
  late GleanDatabase db;
  late CatalogueRepository catalogue;
  var version = 0;

  setUp(() {
    db = createTestDatabase();
    catalogue = CatalogueRepository(db);
    version = 0;
  });
  tearDown(() => db.close());

  // Delivers [items] the way a sync does. The ingredient groups are the seeded ones.
  Future<void> syncItems(List<Map<String, Object?>> items) {
    version += 1;
    return catalogue.applyChanges(
      CatalogueSyncResponse.fromJson(<String, Object?>{
        'version': version,
        'groups': <Object?>[],
        'items': items,
        'aliases': <Object?>[],
      }),
      now: DateTime.utc(2026, 10, 15),
    );
  }

  Future<void> householdOverride(
    String itemId, {
    String? trackingMode,
    String? stockUnit,
    int? unopenedShelfLifeDays,
    int? onceOpenedShelfLifeDays,
    String? section,
  }) => db
      .into(db.ingredientOverrides)
      .insert(
        IngredientOverridesCompanion.insert(
          itemId: itemId,
          trackingMode: Value(trackingMode),
          stockUnit: Value(stockUnit),
          unopenedShelfLifeDays: Value(unopenedShelfLifeDays),
          onceOpenedShelfLifeDays: Value(onceOpenedShelfLifeDays),
          section: Value(section),
        ),
      );

  group('with nothing overridden', () {
    test('an item takes its ingredient group\'s defaults', () async {
      await syncItems([_item('ground-cumin')]);

      final cumin = await catalogue.effectiveIngredient('ground-cumin');

      expect(cumin!.trackingMode, 'presence');
      expect(cumin.stockUnit, isNull);
      expect(cumin.unopenedShelfLifeDays, 365);
      expect(cumin.onceOpenedShelfLifeDays, isNull);
    });

    test('the default for a group with forms is the item\'s form\'s', () async {
      await syncItems([_item('carrot', group: 'root_veg', form: 'fresh')]);

      final carrot = await catalogue.effectiveIngredient('carrot');

      expect(carrot!.trackingMode, 'counted');
      expect(carrot.stockUnit, 'g');
      expect(carrot.unopenedShelfLifeDays, 21);
      expect(carrot.onceOpenedShelfLifeDays, 3);
    });

    test('an id that is not in the catalogue resolves to nothing', () async {
      expect(await catalogue.effectiveIngredient('no-such-item'), isNull);
    });
  });

  group(
    'precedence, field by field: household override, then item, then group',
    () {
      test('tracking mode', () async {
        await syncItems([
          _item('a', group: 'root_veg', form: 'fresh'),
          _item(
            'b',
            group: 'root_veg',
            form: 'fresh',
            overrides: {'tracking_mode': 'perishable'},
          ),
        ]);
        await householdOverride('b', trackingMode: 'presence');

        expect(
          (await catalogue.effectiveIngredient('a'))!.trackingMode,
          'counted',
        );
        await (db.update(
          db.ingredientOverrides,
        )).write(const IngredientOverridesCompanion(trackingMode: Value(null)));
        expect(
          (await catalogue.effectiveIngredient('b'))!.trackingMode,
          'perishable',
        );
        await (db.update(db.ingredientOverrides)).write(
          const IngredientOverridesCompanion(trackingMode: Value('presence')),
        );
        expect(
          (await catalogue.effectiveIngredient('b'))!.trackingMode,
          'presence',
        );
      });

      test('stock unit', () async {
        await syncItems([
          _item('a', group: 'root_veg', form: 'fresh'),
          _item(
            'b',
            group: 'root_veg',
            form: 'fresh',
            overrides: {'stock_unit': 'ml'},
          ),
        ]);

        expect((await catalogue.effectiveIngredient('a'))!.stockUnit, 'g');
        expect((await catalogue.effectiveIngredient('b'))!.stockUnit, 'ml');
        await householdOverride('b', stockUnit: 'count');
        expect((await catalogue.effectiveIngredient('b'))!.stockUnit, 'count');
      });

      test('unopened shelf life', () async {
        await syncItems([
          _item('a', group: 'root_veg', form: 'fresh'),
          _item(
            'b',
            group: 'root_veg',
            form: 'fresh',
            overrides: {'unopened_shelf_life_days': 14},
          ),
        ]);

        expect(
          (await catalogue.effectiveIngredient('a'))!.unopenedShelfLifeDays,
          21,
        );
        expect(
          (await catalogue.effectiveIngredient('b'))!.unopenedShelfLifeDays,
          14,
        );
        await householdOverride('b', unopenedShelfLifeDays: 30);
        expect(
          (await catalogue.effectiveIngredient('b'))!.unopenedShelfLifeDays,
          30,
        );
      });

      test(
        'once-opened shelf life, including over a group with no limit',
        () async {
          await syncItems([
            _item('a', group: 'root_veg', form: 'fresh'),
            _item(
              'b',
              group: 'root_veg',
              form: 'fresh',
              overrides: {'once_opened_shelf_life_days': 7},
            ),
            _item('cumin'),
          ]);

          expect(
            (await catalogue.effectiveIngredient('a'))!.onceOpenedShelfLifeDays,
            3,
          );
          expect(
            (await catalogue.effectiveIngredient('b'))!.onceOpenedShelfLifeDays,
            7,
          );
          await householdOverride('b', onceOpenedShelfLifeDays: 10);
          expect(
            (await catalogue.effectiveIngredient('b'))!.onceOpenedShelfLifeDays,
            10,
          );
          await householdOverride('cumin', onceOpenedShelfLifeDays: 180);
          expect(
            (await catalogue.effectiveIngredient(
              'cumin',
            ))!.onceOpenedShelfLifeDays,
            180,
          );
        },
      );

      test('overriding one field leaves every other field as it was', () async {
        await syncItems([
          _item(
            'ginger',
            group: 'root_veg',
            form: 'fresh',
            overrides: {
              'tracking_mode': 'perishable',
              'once_opened_shelf_life_days': 14,
            },
          ),
        ]);
        await householdOverride('ginger', unopenedShelfLifeDays: 40);

        final ginger = await catalogue.effectiveIngredient('ginger');

        expect(ginger!.unopenedShelfLifeDays, 40);
        expect(ginger.trackingMode, 'perishable');
        expect(ginger.onceOpenedShelfLifeDays, 14);
      });

      test('an item that is not counted has no stock unit, whatever its '
          'group or override says', () async {
        await syncItems([
          _item(
            'a',
            group: 'root_veg',
            form: 'fresh',
            overrides: {'tracking_mode': 'perishable'},
          ),
          _item('cumin'),
        ]);
        await householdOverride('cumin', trackingMode: 'counted');

        expect((await catalogue.effectiveIngredient('a'))!.stockUnit, isNull);
        expect(
          (await catalogue.effectiveIngredient('cumin'))!.stockUnit,
          isNull,
        );
        await (db.update(
          db.ingredientOverrides,
        )).write(const IngredientOverridesCompanion(stockUnit: Value('g')));
        expect((await catalogue.effectiveIngredient('cumin'))!.stockUnit, 'g');
      });
    },
  );
}
