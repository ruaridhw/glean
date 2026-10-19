// Resolves ingredient identities. Resolving an existing ingredient upgrades an unclassified group to a newly
// supplied one, so a group-less ingredient (e.g. from recipe import) cannot permanently poison pantry/shopping rows
// that later resolve it with a real group.
import 'package:drift/drift.dart';

import '../database.dart';
import '../seed/taxonomy.dart' show otherGroupId;
import '../util/unit_normalization.dart' show canonicalUnitFor;

class IngredientsRepository {
  IngredientsRepository(this._db);

  final GleanDatabase _db;

  /// Resolves an ingredient through the catalogue first: the item named by [catalogueItemId], else the item
  /// [canonicalName] or an alias of it resolves to (a merged item following its redirect), reusing the oldest
  /// ingredient already linked to that item. Failing that it uses the ingredient with exactly that name, linking it,
  /// or creates one linked to the item. With no matching item it is a plain name lookup. `groupId` must be null or a
  /// key in `ingredient_groups`; the foreign key makes an invalid group throw.
  ///
  /// Intake passes the group the backend classified, or null when it could not: such an ingredient reads back with
  /// food group "other" until a later resolve supplies a group. Recipe import passes null (recipe endpoints return no
  /// group). Form is never set here: nobody has stated it.
  ///
  /// [unit], when supplied, seeds/upgrades `canonicalUnit`, the target `PantryRepository.addItem` normalises
  /// every future add into. It derives from the first unit the ingredient is resolved with. A recognised
  /// mass/volume unit collapses to its base (`canonicalUnitFor('kg') == 'g'`, `'l'` to `'ml'`), including for
  /// the first add; an unrecognised count-based unit (`'clove'`) becomes canonical verbatim, so a later
  /// incompatible add fails loudly in `PantryRepository._upsert`.
  ///
  /// Callers must never pass a fallback/defaulted string: the seeded value is permanent and shared by every
  /// user (`ingredients` isn't user-scoped), so a guess like `'units'` would be locked in for everyone.
  /// `PantryRepository.addItem` and `ShoppingRepository.addAiItems` apply their storage fallback after this call.
  ///
  /// Recipe import never passes a unit: a recipe's unit reflects its phrasing, not how the ingredient is stocked.
  Future<Ingredient> resolveOrCreate({
    required String canonicalName,
    String? catalogueItemId,
    String? apiName,
    String? groupId,
    String? unit,
  }) async {
    final name = canonicalName.toLowerCase().trim();

    // Identity comes from the catalogue first: the item the caller names, else the one the name or an alias
    // resolves to. An ingredient already linked to that item is the household's one ingredient for it.
    final String? itemId = catalogueItemId != null
        ? await _db.survivingCatalogueItemId(catalogueItemId)
        : await _db.catalogueItemIdForName(name);
    if (itemId != null) {
      final byItem = await _findByCatalogueItem(itemId);
      if (byItem != null) {
        return _upgradeIfNeeded(byItem, groupId, unit);
      }
    }

    final byName = await _findByName(name);
    if (byName != null) {
      return _upgradeIfNeeded(byName, groupId, unit, catalogueItemId: itemId);
    }

    final id = await _db
        .into(_db.ingredients)
        .insert(
          IngredientsCompanion.insert(
            canonicalName: name,
            catalogueItemId: Value(itemId),
            apiName: Value(apiName),
            groupId: Value(groupId),
            canonicalUnit: Value(unit == null ? null : canonicalUnitFor(unit)),
          ),
        );
    return (_db.select(
      _db.ingredients,
    )..where((t) => t.id.equals(id))).getSingle();
  }

  /// The ingredient group of each of [ids] that has one; ingredients without a group are left out.
  Future<Map<int, String>> groupsById(Iterable<int> ids) async {
    final rows = await (_db.select(
      _db.ingredients,
    )..where((t) => t.id.isIn(ids.toList()))).get();
    return {
      for (final row in rows)
        if (row.groupId != null) row.id: row.groupId!,
    };
  }

  // Several rows may name one item, directly or by a former id it absorbed in a merge, so the oldest wins, always.
  Future<Ingredient?> _findByCatalogueItem(String itemId) async {
    final ids = (await _db.catalogueIdentity(itemId)).toList();
    return (_db.select(_db.ingredients)
          ..where((t) => t.catalogueItemId.isIn(ids))
          ..orderBy([(t) => OrderingTerm.asc(t.id)])
          ..limit(1))
        .getSingleOrNull();
  }

  Future<Ingredient?> _findByName(String name) {
    return (_db.select(
      _db.ingredients,
    )..where((t) => t.canonicalName.equals(name))).getSingleOrNull();
  }

  /// Fills in whichever of `groupId`/`canonicalUnit`/`catalogueItemId` is unset on [existing] and newly supplied; an
  /// already-set value is left alone (first real value wins). Other counts as unset for the group: it is where an
  /// unclassified ingredient lands, so a later real group still replaces it.
  Future<Ingredient> _upgradeIfNeeded(
    Ingredient existing,
    String? groupId,
    String? unit, {
    String? catalogueItemId,
  }) async {
    final bool groupUnset =
        existing.groupId == null || existing.groupId == otherGroupId;
    final companion = IngredientsCompanion(
      groupId: groupUnset && groupId != null && groupId != existing.groupId
          ? Value(groupId)
          : const Value.absent(),
      canonicalUnit: existing.canonicalUnit == null && unit != null
          ? Value(canonicalUnitFor(unit))
          : const Value.absent(),
      catalogueItemId:
          existing.catalogueItemId == null && catalogueItemId != null
          ? Value(catalogueItemId)
          : const Value.absent(),
    );
    if (!companion.groupId.present &&
        !companion.canonicalUnit.present &&
        !companion.catalogueItemId.present) {
      return existing;
    }
    await (_db.update(
      _db.ingredients,
    )..where((t) => t.id.equals(existing.id))).write(companion);
    return existing.copyWithCompanion(companion);
  }
}
