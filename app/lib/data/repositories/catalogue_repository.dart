import 'dart:convert';

import 'package:drift/drift.dart';

import '../../api/models/catalogue.dart';
import '../database.dart';
import '../models/effective_ingredient.dart';

/// The synced copy of the backend catalogue. Everything here is shared reference data, not household data, so
/// nothing is user-scoped.
class CatalogueRepository {
  CatalogueRepository(this._db);

  final GleanDatabase _db;

  /// How far sync has got, or null before the first successful sync.
  Future<CatalogueSyncStateData?> syncState() =>
      _db.select(_db.catalogueSyncState).getSingleOrNull();

  /// What the catalogue item [id] is for this household: field by field, the household's override, else the item's
  /// own, else its ingredient group's default. Null when the item, or the group it names, is not held.
  Future<EffectiveIngredient?> effectiveIngredient(String id) async {
    final item = await (_db.select(
      _db.catalogueItems,
    )..where((t) => t.id.equals(id))).getSingleOrNull();
    if (item == null) return null;
    final group = await (_db.select(
      _db.ingredientGroups,
    )..where((t) => t.id.equals(item.groupId))).getSingleOrNull();
    if (group == null) return null;
    final override = await (_db.select(
      _db.ingredientOverrides,
    )..where((t) => t.itemId.equals(item.id))).getSingleOrNull();
    final unopened =
        jsonDecode(group.unopenedShelfLifeDays) as Map<String, dynamic>;
    final onceOpened =
        jsonDecode(group.onceOpenedShelfLifeDays) as Map<String, dynamic>;
    final trackingMode =
        override?.trackingMode ??
        item.overrideTrackingMode ??
        group.trackingMode;
    return EffectiveIngredient(
      id: item.id,
      name: item.name,
      groupId: item.groupId,
      form: item.form,
      trackingMode: trackingMode,
      stockUnit: trackingMode == 'counted'
          ? override?.stockUnit ?? item.overrideStockUnit ?? group.stockUnit
          : null,
      unopenedShelfLifeDays:
          override?.unopenedShelfLifeDays ??
          item.overrideUnopenedShelfLifeDays ??
          unopened[item.form] as int,
      onceOpenedShelfLifeDays:
          override?.onceOpenedShelfLifeDays ??
          item.overrideOnceOpenedShelfLifeDays ??
          onceOpened[item.form] as int?,
      section: override?.section ?? item.section ?? 'Other',
    );
  }

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
              section: Value(i.section),
            ),
        ]);
        b.insertAllOnConflictUpdate(_db.catalogueItemRedirects, [
          for (final i in changes.items)
            for (final former in i.formerIds)
              CatalogueItemRedirectsCompanion.insert(
                formerId: former,
                itemId: i.id,
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
