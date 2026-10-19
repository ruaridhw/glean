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

  /// Resolves an existing ingredient by catalogue item id (preferred) or canonical name, or creates one. `groupId`
  /// must be null or a key in `ingredient_groups`; the foreign key makes an invalid group throw. A new ingredient
  /// with no [catalogueItemId] is linked to the catalogue item its name matches, if one is already synced.
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

    if (catalogueItemId != null) {
      final byItem = await _findByCatalogueItem(catalogueItemId);
      if (byItem != null) return _upgradeIfNeeded(byItem, groupId, unit);
    }

    final byName = await _findByName(name);
    if (byName != null) {
      return _upgradeIfNeeded(
        byName,
        groupId,
        unit,
        catalogueItemId: catalogueItemId,
      );
    }

    final id = await _db
        .into(_db.ingredients)
        .insert(
          IngredientsCompanion.insert(
            canonicalName: name,
            catalogueItemId: Value(catalogueItemId),
            apiName: Value(apiName),
            groupId: Value(groupId),
            canonicalUnit: Value(unit == null ? null : canonicalUnitFor(unit)),
          ),
        );
    if (catalogueItemId == null) {
      await _db.linkIngredientsToCatalogue(ingredientId: id);
    }
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

  Future<Ingredient?> _findByCatalogueItem(String itemId) {
    return (_db.select(
      _db.ingredients,
    )..where((t) => t.catalogueItemId.equals(itemId))).getSingleOrNull();
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
