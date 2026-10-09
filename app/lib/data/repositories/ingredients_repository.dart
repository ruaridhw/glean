// Resolves ingredient identities. Resolving by an existing name/api-id match upgrades a null category to a
// newly supplied one, so a category-less ingredient (e.g. from recipe import) cannot permanently poison
// pantry/shopping rows that later resolve it with a real category.
import 'package:drift/drift.dart';

import '../database.dart';
import '../util/unit_normalization.dart' show canonicalUnitFor;

class IngredientsRepository {
  IngredientsRepository(this._db);

  final GleanDatabase _db;

  /// Resolves an existing ingredient by api id (preferred) or canonical name, or creates one. `category` must
  /// be null or a key in `ingredient_categories`; the foreign key makes an invalid category throw.
  ///
  /// Pantry and shopping intake must pass a non-null `category` so `food_group` is non-nullable on read.
  /// Recipe import passes null (recipe endpoints return no category).
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
    String? apiIngredientId,
    String? apiName,
    String? category,
    String? unit,
  }) async {
    final name = canonicalName.toLowerCase().trim();

    if (apiIngredientId != null) {
      final byId = await _findByApiId(apiIngredientId);
      if (byId != null) return _upgradeIfNeeded(byId, category, unit);
    }

    final byName = await _findByName(name);
    if (byName != null) return _upgradeIfNeeded(byName, category, unit);

    final id = await _db
        .into(_db.ingredients)
        .insert(
          IngredientsCompanion.insert(
            canonicalName: name,
            apiIngredientId: Value(apiIngredientId),
            apiName: Value(apiName),
            category: Value(category),
            canonicalUnit: Value(unit == null ? null : canonicalUnitFor(unit)),
          ),
        );
    return (_db.select(
      _db.ingredients,
    )..where((t) => t.id.equals(id))).getSingle();
  }

  Future<Ingredient?> _findByApiId(String apiId) {
    return (_db.select(
      _db.ingredients,
    )..where((t) => t.apiIngredientId.equals(apiId))).getSingleOrNull();
  }

  Future<Ingredient?> _findByName(String name) {
    return (_db.select(
      _db.ingredients,
    )..where((t) => t.canonicalName.equals(name))).getSingleOrNull();
  }

  /// Upgrades whichever of `category`/`canonicalUnit` is null on [existing] and newly supplied; an already-set
  /// value is left alone (first real value wins).
  Future<Ingredient> _upgradeIfNeeded(
    Ingredient existing,
    String? category,
    String? unit,
  ) async {
    final companion = IngredientsCompanion(
      category: existing.category == null && category != null
          ? Value(category)
          : const Value.absent(),
      canonicalUnit: existing.canonicalUnit == null && unit != null
          ? Value(canonicalUnitFor(unit))
          : const Value.absent(),
    );
    if (!companion.category.present && !companion.canonicalUnit.present) {
      return existing;
    }
    await (_db.update(
      _db.ingredients,
    )..where((t) => t.id.equals(existing.id))).write(companion);
    return existing.copyWithCompanion(companion);
  }
}
