// Ported from the Expo app's `src/db/ingredients.ts` (see git history),
// with two behaviour changes:
//
//   1. Resolving by an existing name/api-id match now *upgrades* a null
//      category to a newly-supplied one instead of keeping it forever.
//      Without that, an ingredient first created without a category (e.g.
//      via recipe import, which has no category source — §9's backend
//      change only covers the parse endpoints) would permanently poison any
//      pantry/shopping row that later resolves the same ingredient with a
//      real category, defeating AC-DATA-11.
//   2. `canonicalUnit` is now actually set — the RN original never wrote it
//      either (see git history, same file), which is R-18: with no target,
//      `normalizeUnit` always returned early and mixed-unit pantry adds
//      silently summed a raw quantity under the wrong unit. See
//      `resolveOrCreate`'s doc comment for the rule chosen.
import 'package:drift/drift.dart';

import '../database.dart';
import '../util/unit_normalization.dart' show canonicalUnitFor;

class IngredientsRepository {
  IngredientsRepository(this._db);

  final GleanDatabase _db;

  /// Resolves an existing ingredient by api id (preferred) or canonical
  /// name, or creates one. `category` must be null or a key present in
  /// `ingredient_categories` — the foreign key constraint enforces this at
  /// write time, so an invalid category throws rather than silently
  /// persisting.
  ///
  /// Pantry and shopping intake call sites must always pass a non-null
  /// `category` (the backend now returns one per parsed ingredient, §9) so
  /// that `food_group` ends up non-nullable wherever pantry data is read
  /// (AC-DATA-11). Recipe import passes null because recipe endpoints don't
  /// return a category — that ingredient may still be null-categoried until
  /// something else resolves it with a real one.
  ///
  /// [unit], when supplied, seeds/upgrades `canonicalUnit` (R-18) — the
  /// target `PantryRepository.addItem` normalises every future add for this
  /// ingredient into. **Rule chosen:** the canonical unit is derived from
  /// whichever unit the ingredient is *first* ever resolved with a unit for.
  /// A recognised mass/volume unit collapses to its common base
  /// (`canonicalUnitFor('kg') == 'g'`, `canonicalUnitFor('l') == 'ml'`), so a
  /// later add in a differently-scaled but compatible unit (kg vs g, l vs
  /// tbsp, ...) still converts correctly — including the very first add,
  /// which is normalised into that base immediately since this method
  /// returns the already-updated row before the caller normalises against
  /// it. An unrecognised, typically count-based unit (`'unit'`, `'clove'`,
  /// ...) has no conversion target, so it becomes the canonical unit
  /// verbatim: a later add in a genuinely incompatible unit then has
  /// something concrete to fail loudly against
  /// (`PantryRepository._upsert`) instead of quietly summing under the
  /// wrong unit.
  ///
  /// **Callers must never pass a fallback/defaulted string** (R-23) — only
  /// an explicitly chosen or parsed unit should reach this parameter. Since
  /// the seeded value is permanent (never overwritten once set) and shared
  /// across every user (`ingredients` is one non-user-scoped catalog), a
  /// caller that defaults a blank field to e.g. `'units'` before calling
  /// this would lock that guess in forever, for everyone, with no in-app way
  /// to correct it. `PantryRepository.addItem` and
  /// `ShoppingRepository.addAiItems` both apply their own storage-only
  /// fallback *after* this call decides whether to seed — see either for
  /// the pattern.
  ///
  /// Only called with a real, stock-tracking unit from pantry/shopping
  /// intake (mirroring the category asymmetry above) — recipe import never
  /// passes one, since a recipe's unit reflects that recipe's phrasing, not
  /// how the ingredient is actually stocked, and would be the wrong thing to
  /// lock in permanently.
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

  /// Upgrades whichever of `category`/`canonicalUnit` is currently null on
  /// [existing] and was newly supplied, leaving an already-set value alone
  /// in either case — the same "first real value wins, and stays" rule for
  /// both fields (see `resolveOrCreate`'s doc comment for why each one in
  /// particular is deliberately never overwritten once set).
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
