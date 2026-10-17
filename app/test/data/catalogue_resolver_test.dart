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
      fullSync: version == 1,
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

    test('an item in a group with no shelf life never expires: null, not zero '
        'and not an error', () async {
      await syncItems([_item('toilet-roll', group: 'household')]);

      final roll = await catalogue.effectiveIngredient('toilet-roll');

      expect(roll, isNotNull);
      expect(roll!.unopenedShelfLifeDays, isNull);
      expect(roll.onceOpenedShelfLifeDays, isNull);
    });

    test(
      'a group that never expires is not the same as an unset item '
      'override: unset inherits the group, whatever the group says',
      () async {
        await syncItems([
          _item('toilet-roll', group: 'household'),
          _item('milk', group: 'dairy'),
        ]);

        expect(
          (await catalogue.effectiveIngredient(
            'toilet-roll',
          ))!.unopenedShelfLifeDays,
          isNull,
          reason: 'the group says never expires',
        );
        expect(
          (await catalogue.effectiveIngredient('milk'))!.unopenedShelfLifeDays,
          7,
          reason: 'the item override is unset, so the group\'s 7 days apply',
        );
      },
    );

    test('an item\'s own days win over a group that never expires', () async {
      await syncItems([
        _item(
          'baby-formula',
          group: 'baby',
          overrides: {'unopened_shelf_life_days': 730},
        ),
      ]);

      final formula = await catalogue.effectiveIngredient('baby-formula');

      expect(formula!.unopenedShelfLifeDays, 730);
      expect(formula.onceOpenedShelfLifeDays, isNull);
    });

    test('a household override gives a never-expiring item a shelf life '
        'without changing the item', () async {
      await syncItems([_item('toilet-roll', group: 'household')]);
      await householdOverride('toilet-roll', unopenedShelfLifeDays: 90);

      expect(
        (await catalogue.effectiveIngredient(
          'toilet-roll',
        ))!.unopenedShelfLifeDays,
        90,
      );
      final stored = await db.select(db.catalogueItems).getSingle();
      expect(stored.overrideUnopenedShelfLifeDays, isNull);
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

  group('store section', () {
    test('is the household\'s override, else the section the item was synced '
        'with, else Other', () async {
      await syncItems([
        _item(
          'onion',
          group: 'onions_and_garlic',
          form: 'fresh',
          section: 'Fruit & Veg',
        ),
        _item('mystery'),
      ]);

      expect(
        (await catalogue.effectiveIngredient('onion'))!.section,
        'Fruit & Veg',
      );
      expect(
        (await catalogue.effectiveIngredient('mystery'))!.section,
        'Other',
      );

      await householdOverride('onion', section: 'Baking');
      await householdOverride('mystery', section: 'Pet');

      expect((await catalogue.effectiveIngredient('onion'))!.section, 'Baking');
      expect((await catalogue.effectiveIngredient('mystery'))!.section, 'Pet');
    });

    test(
      'an override survives a sync that changes the item\'s own section',
      () async {
        await syncItems([
          _item(
            'onion',
            group: 'onions_and_garlic',
            form: 'fresh',
            section: 'Fruit & Veg',
          ),
        ]);
        await householdOverride('onion', section: 'Baking');

        await syncItems([
          _item(
            'onion',
            group: 'onions_and_garlic',
            form: 'fresh',
            section: 'Bakery',
          ),
        ]);

        expect(
          (await catalogue.effectiveIngredient('onion'))!.section,
          'Baking',
        );
      },
    );
  });

  group('a merged item', () {
    test('asked for by a former id, resolves to the surviving item', () async {
      await syncItems([
        _item('coriander', group: 'fresh_herbs', formerIds: ['cilantro']),
      ]);

      final resolved = await catalogue.effectiveIngredient('cilantro');

      expect(resolved!.id, 'coriander');
      expect(resolved.name, 'coriander');
    });

    test(
      'keeps a household override that was keyed on the former id',
      () async {
        await syncItems([
          _item('coriander', group: 'fresh_herbs', formerIds: ['cilantro']),
        ]);
        await householdOverride(
          'cilantro',
          unopenedShelfLifeDays: 9,
          section: 'Baking',
        );

        final resolved = await catalogue.effectiveIngredient('coriander');

        expect(resolved!.unopenedShelfLifeDays, 9);
        expect(resolved.section, 'Baking');
      },
    );

    test('takes the surviving id\'s override first, then a former id\'s, '
        'then the item\'s own value, field by field', () async {
      await syncItems([
        _item(
          'coriander',
          group: 'fresh_herbs',
          formerIds: ['cilantro', 'fresh-coriander'],
          overrides: {
            'unopened_shelf_life_days': 4,
            'once_opened_shelf_life_days': 2,
          },
        ),
      ]);
      await householdOverride('coriander', unopenedShelfLifeDays: 8);
      await householdOverride(
        'cilantro',
        unopenedShelfLifeDays: 99,
        onceOpenedShelfLifeDays: 6,
      );
      await householdOverride('fresh-coriander', section: 'Pet');

      final resolved = await catalogue.effectiveIngredient('cilantro');

      expect(resolved!.unopenedShelfLifeDays, 8);
      expect(resolved.onceOpenedShelfLifeDays, 6);
      expect(resolved.section, 'Pet');
      expect(resolved.trackingMode, 'perishable');
    });

    test('is resolved when the sync delivering the merge arrives after the '
        'override already exists', () async {
      await syncItems([
        _item('cilantro', group: 'fresh_herbs'),
        _item('coriander', group: 'fresh_herbs'),
      ]);
      await householdOverride('cilantro', unopenedShelfLifeDays: 12);
      expect((await catalogue.effectiveIngredient('cilantro'))!.id, 'cilantro');

      await syncItems([
        _item('coriander', group: 'fresh_herbs', formerIds: ['cilantro']),
      ]);

      final resolved = await catalogue.effectiveIngredient('cilantro');
      expect(resolved!.id, 'coriander');
      expect(resolved.unopenedShelfLifeDays, 12);
      expect(
        (await catalogue.effectiveIngredient(
          'coriander',
        ))!.unopenedShelfLifeDays,
        12,
      );
    });

    test('through a chain of merges, still reaches the survivor with the '
        'oldest id\'s override', () async {
      await syncItems([
        _item('c', group: 'fresh_herbs', formerIds: ['b']),
        _item('b', group: 'fresh_herbs', formerIds: ['a']),
      ]);
      await householdOverride('a', unopenedShelfLifeDays: 5);

      final resolved = await catalogue.effectiveIngredient('a');

      expect(resolved!.id, 'c');
      expect(resolved.unopenedShelfLifeDays, 5);
    });

    test('that was merged into each other by mistake still resolves, rather '
        'than looping', () async {
      await syncItems([
        _item('a', group: 'fresh_herbs', formerIds: ['b']),
        _item('b', group: 'fresh_herbs', formerIds: ['a']),
      ]);

      final resolved = await catalogue
          .effectiveIngredient('a')
          .timeout(const Duration(seconds: 5));

      expect(resolved, isNotNull);
    });
  });
}
