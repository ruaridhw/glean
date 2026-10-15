import 'dart:convert';

import 'package:drift/drift.dart';

import '../../api/models/catalogue.dart';
import '../database.dart';

/// The synced copy of the backend catalogue. Everything here is shared reference data, not household data, so
/// nothing is user-scoped.
class CatalogueRepository {
  CatalogueRepository(this._db);

  final GleanDatabase _db;

  /// The catalogue version the device holds; zero before the first successful sync.
  Future<int> syncedVersion() async {
    final state = await _db.select(_db.catalogueSyncState).getSingleOrNull();
    return state?.version ?? 0;
  }

  /// Upserts everything in [changes] by stable id and records its version, all or nothing: a failure part-way
  /// leaves the previous version in place so the same changes are fetched again.
  Future<void> applyChanges(
    CatalogueSyncResponse changes, {
    required DateTime now,
  }) {
    return _db.transaction(() async {
      await _db.batch((b) {
        b.insertAllOnConflictUpdate(_db.ingredientGroups, [
          for (final g in changes.groups)
            IngredientGroupsCompanion.insert(
              id: g.id,
              name: g.name,
              kind: g.kind,
              foodGroup: g.foodGroup,
              trackingMode: g.trackingMode,
              stockUnit: Value(g.stockUnit),
              allowedForms: jsonEncode(g.allowedForms),
              unopenedShelfLifeDays: jsonEncode(g.unopenedShelfLifeDays),
              onceOpenedShelfLifeDays: jsonEncode(g.onceOpenedShelfLifeDays),
            ),
        ]);
        b.insertAllOnConflictUpdate(_db.catalogueItems, [
          for (final i in changes.items)
            CatalogueItemsCompanion.insert(
              id: i.id,
              name: i.name,
              groupId: i.group,
              form: i.form,
              source: i.source,
              densityGPerMl: Value(i.densityGPerMl),
              overrideTrackingMode: Value(i.overrides.trackingMode),
              overrideStockUnit: Value(i.overrides.stockUnit),
              overrideUnopenedShelfLifeDays: Value(
                i.overrides.unopenedShelfLifeDays,
              ),
              overrideOnceOpenedShelfLifeDays: Value(
                i.overrides.onceOpenedShelfLifeDays,
              ),
            ),
        ]);
        b.insertAllOnConflictUpdate(_db.catalogueAliases, [
          for (final a in changes.aliases)
            CatalogueAliasesCompanion.insert(
              key: a.key,
              name: a.name,
              itemId: a.itemId,
            ),
        ]);
        b.insert(
          _db.catalogueSyncState,
          CatalogueSyncStateCompanion.insert(
            id: const Value(1),
            version: changes.version,
            syncedAt: now.toUtc().toIso8601String(),
          ),
          mode: InsertMode.insertOrReplace,
        );
      });
    });
  }
}
