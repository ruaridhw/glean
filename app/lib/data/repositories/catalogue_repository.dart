import 'dart:convert';

import 'package:drift/drift.dart';

import '../../api/models/catalogue.dart';
import '../database.dart';

/// The synced copy of the backend catalogue. Everything here is shared reference data, not household data, so
/// nothing is user-scoped.
class CatalogueRepository {
  CatalogueRepository(this._db);

  final GleanDatabase _db;

  /// How far sync has got, or null before the first successful sync.
  Future<CatalogueSyncStateData?> syncState() =>
      _db.select(_db.catalogueSyncState).getSingleOrNull();

  /// Upserts everything in [changes] by stable id and records its version, all or nothing: a failure part-way
  /// leaves the previous version in place so the same changes are fetched again. [fullSync] marks [changes] as
  /// the answer to a `since=0` request, which restarts the clock on the next full sync.
  Future<void> applyChanges(
    CatalogueSyncResponse changes, {
    required DateTime now,
    required bool fullSync,
  }) {
    return _db.transaction(() async {
      final String nowText = now.toUtc().toIso8601String();
      final String fullSyncedAt = fullSync
          ? nowText
          : (await syncState())?.fullSyncedAt ?? nowText;
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
            syncedAt: nowText,
            fullSyncedAt: fullSyncedAt,
          ),
          mode: InsertMode.insertOrReplace,
        );
      });
    });
  }
}
