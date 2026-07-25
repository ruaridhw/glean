// Ported from `mobile/src/db/ingredients.ts`, with one behaviour change:
// resolving by an existing name/api-id match now *upgrades* a null category
// to a newly-supplied one instead of keeping it forever. Without that, an
// ingredient first created without a category (e.g. via recipe import,
// which has no category source — §9's backend change only covers the parse
// endpoints) would permanently poison any pantry/shopping row that later
// resolves the same ingredient with a real category, defeating AC-DATA-11.
import 'package:drift/drift.dart';

import '../database.dart';

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
  Future<Ingredient> resolveOrCreate({
    required String canonicalName,
    String? apiIngredientId,
    String? apiName,
    String? category,
  }) async {
    final name = canonicalName.toLowerCase().trim();

    if (apiIngredientId != null) {
      final byId = await _findByApiId(apiIngredientId);
      if (byId != null) return _upgradeCategoryIfNeeded(byId, category);
    }

    final byName = await _findByName(name);
    if (byName != null) return _upgradeCategoryIfNeeded(byName, category);

    final id = await _db
        .into(_db.ingredients)
        .insert(
          IngredientsCompanion.insert(
            canonicalName: name,
            apiIngredientId: Value(apiIngredientId),
            apiName: Value(apiName),
            category: Value(category),
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

  Future<Ingredient> _upgradeCategoryIfNeeded(
    Ingredient existing,
    String? category,
  ) async {
    if (existing.category != null || category == null) return existing;
    await (_db.update(_db.ingredients)..where((t) => t.id.equals(existing.id)))
        .write(IngredientsCompanion(category: Value(category)));
    return existing.copyWith(category: Value(category));
  }
}
