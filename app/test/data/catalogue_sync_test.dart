import 'dart:convert';
import 'dart:io';

import 'package:drift/drift.dart' show Value;
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/api.dart';
import 'package:glean/data/catalogue_sync.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/repositories/catalogue_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'fixture.dart';

final List<dynamic> _groups =
    jsonDecode(
          File('test/data/fixtures/catalogue_groups.json').readAsStringSync(),
        )
        as List<dynamic>;

Map<String, Object?> _item(
  String id,
  String name, {
  String group = 'spices',
  String form = 'not_applicable',
  String source = 'seed',
  Map<String, Object?> overrides = const <String, Object?>{},
  String? section,
  List<String>? formerIds,
}) => <String, Object?>{
  'id': id,
  'name': name,
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
  'source': source,
  'section': ?section,
  'former_ids': ?formerIds,
};

Map<String, Object?> _alias(String key, String itemId, [String? name]) =>
    <String, Object?>{'key': key, 'name': name ?? key, 'item_id': itemId};

String _body({
  required int version,
  List<Map<String, Object?>> items = const [],
  List<Map<String, Object?>> aliases = const [],
}) => jsonEncode(<String, Object?>{
  'version': version,
  'groups': _groups,
  'items': items,
  'aliases': aliases,
});

void main() {
  late GleanDatabase db;
  late List<Uri> requests;
  late List<http.Response Function(http.Request)> script;
  late CatalogueSync sync;
  late DateTime clock;

  setUp(() {
    db = createTestDatabase();
    clock = DateTime.utc(2026, 10, 15, 9);
    requests = <Uri>[];
    script = <http.Response Function(http.Request)>[];
    final client = MockClient((http.Request request) async {
      requests.add(request.url);
      return script.removeAt(0)(request);
    });
    sync = CatalogueSync(
      api: GleanApiClient(baseUrl: 'http://api.test', httpClient: client),
      repository: CatalogueRepository(db),
      now: () => clock,
    );
  });
  tearDown(() => db.close());

  void respond(String body, [int status = 200]) =>
      script.add((_) => http.Response(body, status));

  Future<int?> storedVersion() async =>
      (await db.select(db.catalogueSyncState).getSingleOrNull())?.version;

  test('a fresh install asks for the full catalogue and stores every item, '
      'alias and the version', () async {
    respond(
      _body(
        version: 3,
        items: [
          _item('ground-cumin', 'ground cumin'),
          _item(
            'tinned-chickpeas',
            'tinned chickpeas',
            group: 'beans_and_pulses',
            form: 'tinned_jarred',
          ),
          _item('toilet-roll', 'toilet roll', group: 'household'),
        ],
        aliases: [
          _alias('ground cumin', 'ground-cumin'),
          _alias('cumin', 'ground-cumin'),
          _alias('tinned chickpeas', 'tinned-chickpeas'),
          _alias('toilet roll', 'toilet-roll'),
        ],
      ),
    );

    await sync.sync();

    expect(requests.single.path, '/catalogue');
    expect(requests.single.queryParameters['since'], '0');
    final items = await db.select(db.catalogueItems).get();
    expect(
      items.map((i) => i.id),
      unorderedEquals(<String>[
        'ground-cumin',
        'tinned-chickpeas',
        'toilet-roll',
      ]),
    );
    final chickpeas = items.firstWhere((i) => i.id == 'tinned-chickpeas');
    expect(
      (chickpeas.name, chickpeas.groupId, chickpeas.form, chickpeas.source),
      ('tinned chickpeas', 'beans_and_pulses', 'tinned_jarred', 'seed'),
    );
    expect(
      (await db.select(db.catalogueAliases).get()).map((a) => a.key),
      unorderedEquals(<String>[
        'ground cumin',
        'cumin',
        'tinned chickpeas',
        'toilet roll',
      ]),
    );
    expect(await storedVersion(), 3);
  });

  test(
    'an item is stored with the section the backend computed for it',
    () async {
      respond(
        _body(
          version: 1,
          items: [_item('onion', 'onion', section: 'Fruit & Veg')],
        ),
      );

      await sync.sync();

      expect(
        (await db.select(db.catalogueItems).getSingle()).section,
        'Fruit & Veg',
      );
    },
  );

  test('an item from a backend that sends no section is stored without one, '
      'and a later sync fills it in', () async {
    respond(_body(version: 1, items: [_item('onion', 'onion')]));
    await sync.sync();
    expect((await db.select(db.catalogueItems).getSingle()).section, isNull);

    respond(
      _body(
        version: 2,
        items: [_item('onion', 'onion', section: 'Fruit & Veg')],
      ),
    );
    await sync.sync();

    expect(
      (await db.select(db.catalogueItems).getSingle()).section,
      'Fruit & Veg',
    );
  });

  test('the ids merged into an item are stored as redirects to it', () async {
    respond(
      _body(
        version: 1,
        items: [
          _item(
            'coriander',
            'coriander',
            formerIds: <String>['cilantro', 'fresh-coriander'],
          ),
          _item('parsley', 'parsley'),
        ],
      ),
    );

    await sync.sync();

    final redirects = await db.select(db.catalogueItemRedirects).get();
    expect(
      redirects.map((r) => (r.formerId, r.itemId)),
      unorderedEquals(<(String, String)>[
        ('cilantro', 'coriander'),
        ('fresh-coriander', 'coriander'),
      ]),
    );
  });

  test('a sync leaves the household overrides exactly as they were, even '
      'when it changes the same field on the item', () async {
    respond(
      _body(
        version: 1,
        items: [
          _item(
            'ginger',
            'ginger',
            group: 'root_veg',
            form: 'fresh',
            overrides: <String, Object?>{'unopened_shelf_life_days': 14},
          ),
        ],
      ),
    );
    await sync.sync();
    await db
        .into(db.ingredientOverrides)
        .insert(
          IngredientOverridesCompanion.insert(
            itemId: 'ginger',
            unopenedShelfLifeDays: const Value(30),
            section: const Value('Baking'),
          ),
        );
    final before = await db.select(db.ingredientOverrides).get();

    respond(
      _body(
        version: 2,
        items: [
          _item(
            'ginger',
            'ginger',
            group: 'root_veg',
            form: 'fresh',
            overrides: <String, Object?>{'unopened_shelf_life_days': 21},
            section: 'Fruit & Veg',
          ),
        ],
      ),
    );
    await sync.sync();

    expect(await db.select(db.ingredientOverrides).get(), before);
    expect(before.single.unopenedShelfLifeDays, 30);
  });

  test('a second sync asks only for what changed since the stored version '
      'and, with nothing new, changes nothing', () async {
    respond(
      _body(
        version: 1,
        items: [_item('ground-cumin', 'ground cumin')],
        aliases: [_alias('ground cumin', 'ground-cumin')],
      ),
    );
    await sync.sync();
    final before = await db.select(db.catalogueItems).get();
    respond(_body(version: 1));

    await sync.sync();

    expect(requests.last.queryParameters['since'], '1');
    expect(await db.select(db.catalogueItems).get(), before);
    expect(await storedVersion(), 1);
  });

  test('a provisional item created on the backend appears after the next '
      'sync, beside the items already held', () async {
    respond(
      _body(
        version: 1,
        items: [_item('ground-cumin', 'ground cumin')],
        aliases: [_alias('ground cumin', 'ground-cumin')],
      ),
    );
    await sync.sync();
    respond(
      _body(
        version: 2,
        items: [
          _item(
            'dragon-fruit',
            'dragon fruit',
            group: 'fruit',
            form: 'fresh',
            source: 'llm',
          ),
        ],
        aliases: [
          _alias('dragon fruit', 'dragon-fruit'),
          _alias('pitaya', 'dragon-fruit'),
        ],
      ),
    );

    await sync.sync();

    final items = await db.select(db.catalogueItems).get();
    expect(
      items.map((i) => (i.id, i.source)),
      unorderedEquals(<(String, String)>[
        ('ground-cumin', 'seed'),
        ('dragon-fruit', 'llm'),
      ]),
    );
    expect(
      (await db.select(db.catalogueAliases).get()).map((a) => a.key),
      contains('pitaya'),
    );
    expect(await storedVersion(), 2);
  });

  test('a changed item and a moved alias are upserted by their stable ids, '
      'never duplicated', () async {
    respond(
      _body(
        version: 2,
        items: [_item('coriander', 'coriander', group: 'fresh_herbs')],
        aliases: [
          _alias('coriander', 'coriander'),
          _alias('cilantro', 'coriander'),
        ],
      ),
    );
    await sync.sync();
    respond(
      _body(
        version: 3,
        items: [
          _item(
            'coriander',
            'fresh coriander',
            group: 'fresh_herbs',
            overrides: {'unopened_shelf_life_days': 9},
          ),
        ],
        aliases: [
          _alias('fresh coriander', 'coriander'),
          _alias('cilantro', 'coriander'),
        ],
      ),
    );

    await sync.sync();

    final item = (await db.select(db.catalogueItems).get()).single;
    expect(
      (item.id, item.name, item.overrideUnopenedShelfLifeDays),
      ('coriander', 'fresh coriander', 9),
    );
    final aliases = await db.select(db.catalogueAliases).get();
    expect(
      aliases.map((a) => a.key),
      unorderedEquals(<String>['coriander', 'fresh coriander', 'cilantro']),
    );
  });

  test(
    'a sync also refreshes the ingredient groups from the backend',
    () async {
      final changed = jsonDecode(jsonEncode(_groups)) as List<dynamic>;
      (changed.firstWhere((g) => g['id'] == 'spices')
              as Map<String, dynamic>)['name'] =
          'Spices & seasonings';
      script.add(
        (_) => http.Response(
          jsonEncode(<String, Object?>{
            'version': 0,
            'groups': changed,
            'items': <Object?>[],
            'aliases': <Object?>[],
          }),
          200,
        ),
      );

      await sync.sync();

      final spices = await (db.select(
        db.ingredientGroups,
      )..where((g) => g.id.equals('spices'))).getSingle();
      expect(spices.name, 'Spices & seasonings');
      expect(await db.select(db.ingredientGroups).get(), hasLength(29));
    },
  );

  group('recovering from a catalogue read that missed items', () {
    String sinceOfLast() => requests.last.queryParameters['since']!;

    test('an item the backend missed in one response arrives with the next '
        'full sync, without the item being rewritten', () async {
      // The backend's index lagged: version 1 is reported, its item is not sent.
      respond(_body(version: 1));
      await sync.sync();
      clock = clock.add(const Duration(hours: 1));
      respond(_body(version: 1));
      await sync.sync();
      expect(sinceOfLast(), '1', reason: 'an hour later it is a plain delta');
      expect(await db.select(db.catalogueItems).get(), isEmpty);

      clock = clock.add(const Duration(hours: 24));
      respond(
        _body(
          version: 1,
          items: [
            _item(
              'dragon-fruit',
              'dragon fruit',
              group: 'fruit',
              form: 'fresh',
              source: 'llm',
            ),
          ],
          aliases: [_alias('dragon fruit', 'dragon-fruit')],
        ),
      );
      await sync.sync();

      expect(sinceOfLast(), '0');
      expect(
        (await db.select(db.catalogueItems).get()).single.id,
        'dragon-fruit',
      );
      expect(await storedVersion(), 1);
    });

    test('deltas, however recent, never postpone a due full sync', () async {
      respond(_body(version: 1));
      await sync.sync();
      final DateTime firstFull = clock;
      for (final Duration after in const <Duration>[
        Duration(hours: 6),
        Duration(hours: 12),
        Duration(hours: 18),
        Duration(hours: 23, minutes: 59),
      ]) {
        clock = firstFull.add(after);
        respond(_body(version: 1));
        await sync.sync();
        expect(sinceOfLast(), '1', reason: 'a delta at +$after');
      }
      final state = await db.select(db.catalogueSyncState).getSingle();
      expect(state.fullSyncedAt, firstFull.toIso8601String());

      clock = firstFull.add(const Duration(hours: 24, minutes: 1));
      respond(_body(version: 1));
      await sync.sync();

      expect(sinceOfLast(), '0');
    });

    test('a full sync that fails stays due until one succeeds', () async {
      respond(_body(version: 1));
      await sync.sync();
      clock = clock.add(const Duration(hours: 25));
      script.add((_) => throw const SocketException('offline'));
      await sync.sync();
      expect(sinceOfLast(), '0');

      clock = clock.add(const Duration(minutes: 5));
      respond(_body(version: 2));
      await sync.sync();
      expect(sinceOfLast(), '0');

      clock = clock.add(const Duration(minutes: 5));
      respond(_body(version: 2));
      await sync.sync();
      expect(sinceOfLast(), '2');
    });
  });

  group('when the sync cannot complete', () {
    Future<void> seedOneItem() async {
      respond(
        _body(
          version: 1,
          items: [_item('ground-cumin', 'ground cumin')],
          aliases: [_alias('ground cumin', 'ground-cumin')],
        ),
      );
      await sync.sync();
    }

    final Map<String, http.Response Function(http.Request)> failures = {
      'the network is down': (_) => throw const SocketException('offline'),
      'the session has expired': (_) => http.Response('{"detail":"no"}', 401),
      'the server errors': (_) => http.Response('boom', 502),
      'the response is not the catalogue': (_) => http.Response('<html>', 200),
      'the response is missing its items': (_) =>
          http.Response('{"version": 9, "groups": []}', 200),
    };
    failures.forEach((reason, failure) {
      test('$reason: it does not throw, and the catalogue and version it '
          'held are untouched', () async {
        await seedOneItem();
        script.add(failure);

        await sync.sync();

        expect(
          (await db.select(db.catalogueItems).get()).single.id,
          'ground-cumin',
        );
        expect(await storedVersion(), 1);
        expect(await db.select(db.ingredientGroups).get(), hasLength(29));
      });
    });

    test('a first sync that fails leaves the app on its seeded groups with '
        'no items and no version', () async {
      script.add((_) => throw const SocketException('offline'));

      await sync.sync();

      expect(await db.select(db.catalogueItems).get(), isEmpty);
      expect(await storedVersion(), isNull);
      expect(await db.select(db.ingredientGroups).get(), hasLength(29));
    });

    test('a write that fails part-way stores none of the changes and keeps '
        'the old version, so the same changes are fetched next time', () async {
      await seedOneItem();
      await db.customStatement(
        'CREATE TRIGGER fail_alias BEFORE INSERT ON catalogue_aliases '
        "BEGIN SELECT RAISE(ABORT, 'disk full'); END",
      );
      respond(
        _body(
          version: 2,
          items: [
            _item(
              'dragon-fruit',
              'dragon fruit',
              group: 'fruit',
              form: 'fresh',
            ),
          ],
          aliases: [_alias('dragon fruit', 'dragon-fruit')],
        ),
      );

      await expectLater(sync.sync(), throwsA(anything));

      expect((await db.select(db.catalogueItems).get()).map((i) => i.id), [
        'ground-cumin',
      ]);
      expect(await storedVersion(), 1);
    });
  });

  test('a sync started while another is running joins it instead of making '
      'a second request', () async {
    respond(_body(version: 1));

    await Future.wait(<Future<void>>[sync.sync(), sync.sync()]);

    expect(requests, hasLength(1));
  });

  test('a group with no shelf life is stored as null, not zero, and an item '
      'override of its own is stored beside it', () async {
    respond(
      _body(
        version: 1,
        items: [
          _item(
            'baby-formula',
            'baby formula',
            group: 'baby',
            overrides: {'unopened_shelf_life_days': 730},
          ),
          _item('toilet-roll', 'toilet roll', group: 'household'),
        ],
      ),
    );
    await sync.sync();

    final household = await (db.select(
      db.ingredientGroups,
    )..where((g) => g.id.equals('household'))).getSingle();
    expect(jsonDecode(household.unopenedShelfLifeDays), <String, Object?>{
      'not_applicable': null,
    });
    expect(jsonDecode(household.onceOpenedShelfLifeDays), <String, Object?>{
      'not_applicable': null,
    });
    final items = {
      for (final i in await db.select(db.catalogueItems).get())
        i.id: i.overrideUnopenedShelfLifeDays,
    };
    expect(items, <String, int?>{'baby-formula': 730, 'toilet-roll': null});
  });
}
